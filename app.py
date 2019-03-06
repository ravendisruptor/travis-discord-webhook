import json
import logging
import os
import sys

from flask import Flask, request, Response
import requests
import yaml


PAYLOAD_TITLE = "[{repository[name]}:{branch}] Build #{number} {result_text}"
PAYLOAD_DESCRIPTION = "[`{commit:.7}`]({url}) {message}"
PAYLOAD_COMMIT_URL = "https://github.com/{repository[owner_name]}/{repository[name]}/commit/{commit}"


with open("config.yaml") as file:
    config = yaml.load(file)

# Fetch the env variables from Heroku os.environ for security reasons...
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
DISCORD_WEBHOOK_KARMANOR = os.environ["DISCORD_WEBHOOK_KARMANOR"]
DISCORD_WEBHOOK_AZURE = os.environ["DISCORD_WEBHOOK_AZURE"]

DISCORD_JSON = config["discord-json"]
COLORS = config["colors"]
COLORS_AZURE = config["colors-azure"]

SW_JSON = config["sw-json"]
SW_JSON_ID = config["sw-json-file-id"]

app = Flask(__name__)
# Is this even needed?
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "idk")


@app.route("/badge", methods=["GET"])
def badge():
    # Gets online users
    data = requests.get(DISCORD_JSON)
    data = json.loads(data.text)
    onlineUsersString = str(len(data['members'])) + " Online"

    # Gets total downloaded (from SW and GitHub)
    # Gets lifetime subscriptions from Steam Workshop
    data = requests.post(
        SW_JSON, {"itemcount": 1, "publishedfileids[0]": SW_JSON_ID})
    data = json.loads(data.text)
    totalDownloadsSteam = int(
        data["response"]["publishedfiledetails"][0]["lifetime_subscriptions"])

    # Gets all downloads from GitHub
    data = requests.get(
        'https://api.github.com/repos/ArmaAchilles/Achilles/releases')
    data = json.loads(data.text)
    totalDownloadsGitHub = 0

    # https://github.com/mmilidoni/github-downloads-count/blob/af4ea8ad1148450a4135c1404a58f6719ceb8960/gdc#L63
    for releases in data:
        if "assets" in releases:
            for asset in releases['assets']:
                totalDownloadsGitHub += asset['download_count']

    # get current version
    tagName = data[0]['tag_name']

    # Returns a JSON
    return Response(json.dumps(
        {
            'users': onlineUsersString,
            'downloads': human_format(totalDownloadsSteam + totalDownloadsGitHub),
            'version': tagName.replace("v", "")
        }
    ), mimetype='application/json')

# https://stackoverflow.com/a/579376


def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    # add more suffixes if you need them
    return '{}{}'.format(round(num), ['', 'k', 'm'][magnitude])


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.form["payload"]
    data = json.loads(data)

    if (data["repository"]["owner_name"] != "ArmaAchilles"):
        sys.exit()

    # Force lower because yaml uses lower case
    result = data["status_message"].lower()

    color = COLORS[result]

    time = "started_at" if result == "pending" else "finished_at"

    # PHP example just uses array() but that doesn't make sense...
    # Idk, should ask someone who PHPs
    payload = {
        "username": "Travis CI",
        "avatar_url": "https://i.imgur.com/kOfUGNS.png",
        "embeds": [{
            "color": color,
            "author": {
                "name": data["author_name"]
                # TODO: See if author username can be found in
                # Travis' payload, and then
                # `"icon_url" : "https://github.com/USERNAME.png`
                # as described in https://stackoverflow.com/a/36380674
            },
            "title": PAYLOAD_TITLE.format(**data, result_text=result.capitalize()),
            "url": data["build_url"],
            "description": PAYLOAD_DESCRIPTION.format(**data, url=PAYLOAD_COMMIT_URL.format(**data)),
            "timestamp": data[time]
        }]
    }

    resp = requests.request("POST", DISCORD_WEBHOOK, json=payload, headers={
                            "Content-Type": "application/json"})

    # https://stackoverflow.com/a/19569090
    return resp.text, resp.status_code, resp.headers.items()


@app.route("/webhook_karmanor", methods=["POST"])
def webhook_karmanor():
    data = request.form["payload"]
    data = json.loads(data)

    if (data["repository"]["owner_name"] != "ArmaAchilles"):
        sys.exit()

    # Force lower because yaml uses lower case
    result = data["status_message"].lower()

    color = COLORS[result]

    time = "started_at" if result == "pending" else "finished_at"

    # PHP example just uses array() but that doesn't make sense...
    # Idk, should ask someone who PHPs
    payload = {
        "username": "Travis CI",
        "avatar_url": "https://i.imgur.com/kOfUGNS.png",
        "embeds": [{
            "color": color,
            "author": {
                "name": data["author_name"]
                # TODO: See if author username can be found in
                # Travis' payload, and then
                # `"icon_url" : "https://github.com/USERNAME.png`
                # as described in https://stackoverflow.com/a/36380674
            },
            "title": PAYLOAD_TITLE.format(**data, result_text=result.capitalize()),
            "url": data["build_url"],
            "description": PAYLOAD_DESCRIPTION.format(**data, url=PAYLOAD_COMMIT_URL.format(**data)),
            "timestamp": data[time]
        }]
    }

    resp = requests.request("POST", DISCORD_WEBHOOK_KARMANOR, json=payload, headers={
                            "Content-Type": "application/json"})

    # https://stackoverflow.com/a/19569090
    return resp.text, resp.status_code, resp.headers.items()

@app.route("/azure", methods=["POST"])
def azure():
    data = request.get_json()

    resourceJson = requests.get(data["resource"]["url"]).json()

    if (resourceJson["repository"]["id"] != "ArmaAchilles/Achilles"):
        sys.exit()

    result = resourceJson["result"].lower()

    color = COLORS_AZURE[result]

    commit = requests.get("https://api.github.com/repos/ArmaAchilles/Achilles/commits/" + resourceJson["sourceVersion"]).json()

    branch = resourceJson["sourceBranch"].split('/')[2]

    payload = {
        "username": "Azure Pipelines",
        "avatar_url": "https://i.imgur.com/2PJdoTK.png",
        "embeds": [{
            "color": color,
            "author": {
                "name": commit["author"]["login"],
                "url": commit["author"]["html_url"],
                "icon_url": commit["author"]["avatar_url"]
            },
            "title": "[{repository}:{branch}] Build #{number} {result}".format(
                repository="Achilles", branch=branch, number=resourceJson["id"], result=result.capitalize()
            ),
            "url": resourceJson["_links"]["web"]["href"],
            "description": "[`{commit:.7}`]({url}) {message}".format(
                commit=commit["sha"], url=commit["html_url"], message=commit["commit"]["message"]
            ),
            "timestamp": resourceJson["finishTime"]
        }]
    }

    resp = requests.request("POST", DISCORD_WEBHOOK_AZURE, json=payload, headers={
                            "Content-Type": "application/json"})

    return resp.text, resp.status_code, resp.headers.items()


@app.errorhandler(500)
def server_error(e):
    logging.exception("Error :/")
    return """
    Idk, server error :/

    <pre>{}</pre>

    sorry
    """.format(e), 500


if __name__ == "__main__":
    app.run(debug=True)
