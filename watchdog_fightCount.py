import configparser
import datetime
import logging
import os
import queue
import threading
import tempfile
import time
import zipfile
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple

import requests
import parser
import gw2_data
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

#EXE Icon attribution: https://www.flaticon.com/authors/abdul-aziz

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


MAX_WAIT_TIME = 30  # seconds to wait for file completion
LOG_QUEUE = queue.Queue()
PROCESSED = set()   # deduplication guard


# --- File event handler ---
class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        self.handle_file_event(event)

    def on_modified(self, event):
        self.handle_file_event(event)

    def handle_file_event(self, event):
        if not event.is_directory and event.src_path.endswith((".evtc", ".zevtc")):
            if event.src_path not in PROCESSED:  # prevent duplicates
                LOG_QUEUE.put(event.src_path)
                PROCESSED.add(event.src_path)                
                logger.info(
                    "Queued file for processing: %s (queue size: %d)",
                    event.src_path,
                    LOG_QUEUE.qsize(),
                )


# --- Worker thread ---
def log_worker():
    while True:
        log_file = LOG_QUEUE.get()  # blocking wait
        if log_file is None:  # shutdown signal
            break

        start_time = datetime.datetime.now()
        _, file_ext = os.path.splitext(log_file)

        try:
            wait_for_file_completion(log_file, file_ext, start_time)
        except Exception as e:
            logger.exception("Error handling %s: %s", log_file, e)

        LOG_QUEUE.task_done()
        logger.info(
            "Finished processing %s (queue size: %d)",
            log_file,
            LOG_QUEUE.qsize(),
        )


def wait_for_file_completion(file_path: str, file_ext: str, start_time: datetime.datetime) -> None:
    last_size = -1
    start_wait = time.time()

    while time.time() - start_wait < MAX_WAIT_TIME:
        try:
            current_size = os.path.getsize(file_path)
            if current_size == last_size and current_size > 0:
                logger.info("File writing complete: %s", file_path)
                process_new_log(file_path, file_ext, start_time)
                return
            last_size = current_size
        except (IOError, PermissionError):
            logger.debug("File %s not yet accessible, waiting...", file_path)
        time.sleep(1)

    logger.warning("Timeout waiting for %s to complete.", file_path)

# --- Agent utilities ---
def set_team_changes(agents: List, events: List) -> None:
    """Assign teams to agents based on event statechanges."""
    team_assignments: Dict[int, int] = {}
    for event in events:
        if event.is_statechange == 22 and event.src_agent:
            assigned_team = event.dst_agent if event.dst_agent else event.value
            if assigned_team != 0:
                team_assignments[event.src_agent] = assigned_team

    for agent in agents:
        if agent.is_elite != 4294967295 and not agent.team:
            assigned_team = team_assignments.get(agent.address)
            if assigned_team in gw2_data.team_ids:
                agent.team = gw2_data.team_ids[assigned_team]


def set_agent_instance_id(agents: List, events: List) -> None:
    """Assign first seen instance IDs to agents."""
    instance_ids: Dict[int, int] = {}
    for event in events:
        if event.is_statechange != 22 and event.src_instid and event.src_agent:
            if event.src_agent not in instance_ids:
                instance_ids[event.src_agent] = event.src_instid

    for agent in agents:
        if agent.is_elite != 4294967295 and not agent.instid:
            instid = instance_ids.get(agent.address)
            if instid:
                agent.instid = instid


def summarize_non_squad_players(
    agents: List,
) -> Tuple[int, Dict[int, Counter], Dict[str, Counter], Optional[int]]:
    """
    Summarize squad and non-squad players.
    Returns: (squad_count, non_squad_summary, squad_comp, squad_color)
    """
    non_squad_summary: Dict[int, Counter] = defaultdict(Counter)
    squad_comp: Dict[str, Counter] = defaultdict(Counter)
    squad_id: set[int] = set()
    duplicate_check: set[int] = set()
    squad_color: Optional[int] = None
    squad_count = 0

    for agent in agents:
        if agent.is_elite == 4294967295 or agent.instid is None or agent.team is None:
            continue

        if ":" in agent.name:  # Squad
            if agent.instid not in squad_id:
                squad_id.add(agent.instid)
                squad_count += 1
                agent_prof = gw2_data.elites.get(
                    agent.is_elite, gw2_data.profs[agent.profession]
                )
                squad_comp["Squad"][agent_prof] += 1
            if squad_color is None:
                squad_color = agent.team
        elif agent.instid not in duplicate_check:
            duplicate_check.add(agent.instid)
            agent_prof = gw2_data.elites.get(
                agent.is_elite, gw2_data.profs[agent.profession]
            )
            non_squad_summary[agent.team][agent_prof] += 1

    return squad_count, non_squad_summary, squad_comp, squad_color

# --- Discord integration ---
def send_to_discord(
    webhook_url: str,
    file_path: str,
    summary: Dict,
    squad_count: int,
    squad_comp: Dict,
    squad_color: Optional[int],
) -> None:
    """Send analysis results to Discord via webhook."""
    DISCORD_EMOJI = {"Red": ":red_square:", "Green": ":green_square:", "Blue": ":blue_square:"}

    if not summary:
        payload = {"content": f"No valid data to analyze in {os.path.basename(file_path)}"}
    else:
        embed = {
            "title": f"Player counts for fight: {os.path.basename(file_path)}",
            "color": 5793266,  # Blurple
            "fields": [],
            "author": {
                "icon_url": "https://wiki.guildwars2.com/images/c/cb/Commander_tag_%28purple%29.png",
                "name": "LogMon",
            },
            "footer": {"text": "Drevarr's Fight Log Monitor"},
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }

        # Team reports
        for team in sorted(summary.keys()):
            team_report = "|"
            team_count = sum(summary[team].values())
            sorted_team = dict(
                sorted(summary[team].items(), key=lambda item: item[1], reverse=True)
            )
            team_emoji = DISCORD_EMOJI.get(team, "")
            for prof in sorted_team:
                team_report += f" {gw2_data.prof_abbrv[prof]}: {sorted_team[prof]} |"
            embed["fields"].append(
                {
                    "name": f"{team_emoji} Team {'Allies' if team == squad_color else team}: {team_count}",
                    "value": team_report,
                    "inline": False,
                }
            )

        # Squad info
        embed["fields"].append(
            {"name": ":pink_heart: Squad Count:", "value": f"{squad_count} squad members", "inline": False}
        )
        squad_report = "|" + " ".join(
            f"{gw2_data.prof_abbrv[prof]}: {squad_comp['Squad'][prof]} |" for prof in squad_comp["Squad"]
        )
        embed["fields"].append(
            {"name": "Squad Composition:", "value": squad_report, "inline": False}
        )

        payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Successfully sent analysis to Discord for %s", file_path)
    except Exception as e:
        logger.error("Error sending to Discord: %s", e)

# --- Log processing ---
def process_new_log(log_file: str, file_ext: str, start_time: datetime.datetime) -> None:
    logger.info("Starting processing of %s", log_file)
    agents, skills, events, header = [], [], [], None

    try:
        if file_ext.lower() == ".zevtc":
            logger.info("Processing .zevtc file: %s", log_file)
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(log_file, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                for extracted_file in os.listdir(temp_dir):
                    extracted_path = os.path.join(temp_dir, extracted_file)
                    logger.debug("Extracted file: %s", extracted_path)
                    last_size = -1
                    start_wait = time.time()
                    while time.time() - start_wait < MAX_WAIT_TIME:
                        try:
                            current_size = os.path.getsize(extracted_path)
                            if current_size == last_size and current_size > 0:
                                logger.info("Parsing extracted file: %s", extracted_path)
                                header, agents, skills, events = parser.parse_evtc(extracted_path)
                                break
                            last_size = current_size
                        except (IOError, PermissionError):
                            logger.debug("File %s not yet accessible", extracted_path)
                        time.sleep(1)
                    else:
                        logger.warning("Timeout waiting for %s to complete.", extracted_path)
                        return

        elif file_ext.lower() == ".evtc":
            logger.info("Processing .evtc file: %s", log_file)
            if os.path.getsize(log_file) == 0:
                logger.error("Error: %s is empty", log_file)
                return
            with open(log_file, "rb") as f:
                header_bytes = f.read(12)
                if not header_bytes.startswith(b"EVTC"):
                    logger.error("Error: %s is not a valid EVTC file", log_file)
                    return
            header, agents, skills, events = parser.parse_evtc(log_file)
            if not all([header, agents, skills, events]):
                logger.error("Error: Incomplete data from parser for %s", log_file)
                return
            logger.info("Parsed %s: %d agents, %d skills, %d events", log_file, len(agents), len(skills), len(events))

    except zipfile.BadZipFile as e:
        logger.error("Failed to extract %s: %s", log_file, e)
        return
    except Exception as e:
        logger.exception("Error processing %s: %s", log_file, e)
        return

    logger.info("Setting team changes for %d agents", len(agents))
    set_team_changes(agents, events)

    logger.info("Setting agent instance IDs")
    set_agent_instance_id(agents, events)

    logger.info("Summarizing non-squad players")
    squad_count, team_report, squad_comp, squad_color = summarize_non_squad_players(agents)
    logger.info("Squad players: %d", squad_count)

    end_time = datetime.datetime.now()
    logger.info("File %s processed, %d agents, %d skills, %d events", log_file, len(agents), len(skills), len(events))
    logger.info("Processing Time: %s", end_time - start_time)

    if WEBHOOK_URL:
        logger.info("Sending to Discord webhook: %s", WEBHOOK_URL)
        send_to_discord(WEBHOOK_URL, log_file, team_report, squad_count, squad_comp, squad_color)
    else:
        logger.warning("No WEBHOOK_URL configured, skipping Discord send")
        print("\n===== Log Summary =====")
        print(f"File: {os.path.basename(log_file)}")
        print(f"Squad members: {squad_count}")
        print("Squad composition:")
        squad_comp_line = ""
        for prof, count in squad_comp["Squad"].items():
            squad_comp_line += f"{gw2_data.prof_abbrv[prof]}: {count}, "
        print(f"  {squad_comp_line.rstrip(', ')}")

        if not team_report:
            print("No non-squad players found.")
        else:
            for team, counter in team_report.items():
                team_count = sum(counter.values())
                team_name = "Allies" if team == squad_color else f"Team {team}"
                print(f"\n{team_name} ({team_count} players):")
                prof_count_line = ""
                for prof, count in counter.items():
                    prof_count_line += f"{gw2_data.prof_abbrv[prof]}: {count}, "
                print(f"  {team_name} Comp: {prof_count_line.rstrip(', ')}")
        print("========================\n")

    parser.free_evtc_data(header, agents, skills, events)


# --- Main entry ---
if __name__ == "__main__":
    config_ini = configparser.ConfigParser()
    config_ini.read("config.ini")

    ARCDPS_LOG_DIR = config_ini["Settings"]["ARCDPS_LOG_DIR"]
    if not os.path.isdir(ARCDPS_LOG_DIR):
        raise ValueError(f"Directory {ARCDPS_LOG_DIR} does not exist or is not a directory")
    if not os.access(ARCDPS_LOG_DIR, os.R_OK):
        raise ValueError(f"No read permission for directory {ARCDPS_LOG_DIR}")

    LOG_DELAY = int(config_ini["Settings"].get("LOG_DELAY", 5))
    WEBHOOK_URL = config_ini["Settings"]["WEBHOOK_URL"]

    # Start worker thread
    worker = threading.Thread(target=log_worker, daemon=True)
    worker.start()

    logger.info("Watching for new ArcDps logs in %s", ARCDPS_LOG_DIR)
    event_handler = MyHandler()
    observer = PollingObserver()  # PollingObserver is more reliable cross-platform
    observer.schedule(event_handler, ARCDPS_LOG_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        LOG_QUEUE.put(None)  # signal worker to stop
        worker.join()

    observer.join()