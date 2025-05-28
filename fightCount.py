import parser
import datetime
import os
import time
import zipfile
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

prof_abbrv = {
    "Guardian":"Gn", "Dragonhunter":"Dh", "Firebrand":"Fb", "Willbender":"Wb",
    "Warrior":"War", "Berserker":"Brs", "Spellbreaker":"Spb", "Bladesworn":"Bds",
    "Engineer":"Eng", "Scrapper":"Scr", "Holosmith":"Hol", "Mechanist":"Mec",
    "Ranger":"Rgr", "Druid":"Dru", "Soulbeast":"Slb", "Untamed":"Unt",
    "Thief":"Thf", "Daredevil":"Dar", "Deadeye":"Ded", "Specter":"Spe",
    "Elementalist":"Ele", "Tempest":"Tmp", "Weaver":"Wea", "Catalyst":"Cat",
    "Mesmer":"Mes", "Chronomancer":"Chr", "Mirage":"Mir", "Virtuoso":"Vir",
    "Necromancer":"Nec", "Reaper":"Rea", "Scourge":"Scg", "Harbinger":"Har",
    "Revenant":"Rev", "Herald":"Her", "Renegade":"Ren", "Vindicator":"Vin",    
}

team_colors = {
    0: "Unk",
    705: "Red",
    706: "Red",
    882: "Red",
    2520: "Red",
    2739: "Green",
    2741: "Green",
    2752: "Green",
    2763: "Green",
    432: "Blue",
    1277: "Blue",
}

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        print(f"File created: {event.src_path}")
        time.sleep(2)
        logfile = event.src_path
        start_time = datetime.datetime.now()
        header, agents, skills, events =parser.parse_evtc(logfile)

        team_changes = collect_team_changes(events)
        fight_count = collect_fight_count(agents, team_changes)
        print_fight_count(fight_count)

        end_time = datetime.datetime.now()
        print(f"File: {logfile} processed, {len(agents)} agents, {len(skills)} skills, {len(events)} events")
        print(f"Start Time:\t {start_time}")
        print(f"End Time:\t {end_time}")
        print(f"Processing Time:  {end_time-start_time}")

def collect_team_changes(events):
    team_changes = {}

    for event in events:
        if event.is_statechange == 22:
            agent = event.src_agent
            team = event.value
            team_changes[agent] = team

    return team_changes

def collect_fight_count(agents, team_changes):
    fight_count = {
    'squad':{}
    }

    for agent in agents:
        team = team_changes[agent.address]
        agent_team = team_colors[team]
        if agent_team not in fight_count:
            fight_count[agent_team]={}
            
        if agent.is_elite == 4294967295:
            continue
        if ":" in agent.name:
            name, account, sub = agent.name.split('\x00')
            if sub not in fight_count['squad']:
                fight_count['squad'][sub] = {}
            fight_count['squad'][sub][name] = account

        elif team:
            fight_count[agent_team][prof_abbrv[agent.name]] = fight_count[agent_team].get(prof_abbrv[agent.name], 0) +1

    return fight_count

def print_fight_count(fight_count):
    #Report non-squad players by team color, descending order of profession count
    for teamColor in fight_count:
        if teamColor in ['squad', 'Unk']:
            continue
        sorted_team = dict(sorted(fight_count[teamColor].items(), key=lambda item: item[1], reverse=True))
        team_count = sum(fight_count[teamColor].values())
        print(teamColor, team_count)
        print(sorted_team)
        print(f"-----=====End of {teamColor}=====-----\n")

if __name__ == "__main__":
    path_to_watch = "."  # Replace with the path to the directory you want to monitor
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()