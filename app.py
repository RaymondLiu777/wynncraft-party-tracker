from flask import Flask, jsonify, render_template
import requests
import csv
from werkzeug.middleware.proxy_fix import ProxyFix
from party import players

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

class RateLimitException(Exception):
    def __init__(self, time_to_wait, message="Rate limit exceeded", status_code=429):
        self.message = message
        self.status_code = status_code
        self.time_to_wait = time_to_wait
        super().__init__(self.message)

@app.errorhandler(RateLimitException)
def handle_rate_limit_error(e):
    response = {
        "error": "rate_limit_exceeded",
        "message": e.message + " please wait " + str(e.time_to_wait) + " before refreshing the page"
    }
    return jsonify(response), e.status_code

def getPlayerData():
    data = {}
    for player in players:
        response = requests.get(f'https://api.wynncraft.com/v3/player/{player[1]}/characters/{player[2]}')
        if(int(response.headers["RateLimit-Remaining"]) < 10):
            raise RateLimitException(response.headers["RateLimit-Reset"])
        data[player[0]] = response.json()
        data[player[0]]["Expires"] = response.headers["Expires"]
        data[player[0]]["RateLimit-Remaining"] = response.headers["RateLimit-Remaining"]
        data[player[0]]["RateLimit-Reset"] = response.headers["RateLimit-Reset"]
    return data        

def calculateQuests(data):
    # Get quest data
    player_quest_set = {}
    for player in players:
        player_quest_set[player[0]] = set(data[player[0]]["quests"])
    # Get all fnished quests
    all_finished_quests = set()
    for quest_set in player_quest_set.values():
        all_finished_quests.update(quest_set)
    # find quests people didn't do
    for player in players:
        player_quest_set[player[0]] = all_finished_quests.difference(player_quest_set[player[0]])
    # Get master set of all quests that not everyone has done
    unfinished_quests = set()
    for quest_set in player_quest_set.values():
        unfinished_quests.update(quest_set)
    # Figure out min level
    min_level = 120
    for player in players:
        min_level = min(min_level, data[player[0]]["level"])
    # Get playable quests
    playable_quests = {}
    with open('quests.csv', mode ='r')as file:
        csvFile = csv.reader(file)
        for lines in csvFile:
            if(lines[0] not in all_finished_quests and int(lines[1]) <= min_level):
                playable_quests[lines[0]] = {"level-req": lines[1]}
    return {"players": player_quest_set, "master": unfinished_quests, "recommended": playable_quests}
    
@app.route("/")
def hello_world():
    data = getPlayerData()
    data["quests"] = calculateQuests(data)
    # print(data["quests"])
    for player in players:
        data[player[0]]["uuid"] = player[1]
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)