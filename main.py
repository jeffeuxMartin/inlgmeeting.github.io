# pylint: disable=global-statement,redefined-outer-name
import argparse
import csv
from datetime import datetime
import glob
import json
import os
import re

import yaml
from flask import Flask, jsonify, redirect, render_template, send_from_directory
from flask_frozen import Freezer
from flaskext.markdown import Markdown

site_data = {}
by_uid = {}
by_date = {}

def main(site_data_path):
    global site_data, extra_files
    extra_files = ["Home.md"]
    # Load all for your sitedata one time.
    for f in glob.glob(site_data_path + "/*"):
        print(f)
        extra_files.append(f)
        name, typ = f.split("/")[-1].split(".")
        if typ == "json":
            site_data[name] = json.load(open(f))
        elif typ in {"csv", "tsv"}:
            site_data[name] = list(csv.DictReader(open(f)))
        elif typ == "yml":
            site_data[name] = yaml.load(open(f).read(), Loader=yaml.SafeLoader)

    site_data["papers"] = [format_paper(x) for x in site_data["papers"].values()]
    
    for p in site_data["sessions"]:
        dt = datetime.strptime(p["start_time"], "%Y-%m-%dT%H:%M:%SZ")
        if dt.strftime('%A') not in by_date:
            by_date[dt.strftime('%A')] = {'name': dt.strftime('%A'), 'sessions': {}}
        p["contents"] = []
        p["name"] = p["session"]
        p["start_time"] = dt
        by_date[dt.strftime('%A')]['sessions'][p["session"]] = p
        
    for typ in ["papers", "speakers"]:
        by_uid[typ] = {}
        if typ == "speakers":
            vals = site_data[typ]['speakers']
        elif typ in ["workshops", "tutorials", "panels", "hackathons"]:
            vals = [format_workshop(workshop) for workshop in site_data[typ]]
        else:
            vals = site_data[typ]
            
        for p in vals:
            dt = datetime.strptime(p["start_time"], "%Y-%m-%dT%H:%M:%SZ")
            by_uid[typ][p["UID"]] = p
            by_date[dt.strftime('%A')]['sessions'][p["session"]]['contents'].append(p)
            p["zoom"] = by_date[dt.strftime('%A')]['sessions'][p["session"]]['zoom']
                                                              
        for day in by_date.values():
            day['sessions'] = dict(sorted(day['sessions'].items(), key=lambda item: item[1]["start_time"]))
            for session in day['sessions'].values():
                session['contents'] = sorted(session['contents'], key=lambda item: item["start_time"])

    print("Data Successfully Loaded")
    return extra_files


# ------------- SERVER CODE -------------------->

app = Flask(__name__)
app.config.from_object(__name__)
freezer = Freezer(app)
markdown = Markdown(app)


# MAIN PAGES


def _data():
    data = {}
    data["config"] = site_data["config"]
    return data


@app.route("/")
def index():
    return redirect("/index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(site_data_path, "favicon.ico")


# TOP LEVEL PAGES


@app.route("/index.html")
def home():
    data = _data()
    data["home"] = open("Home.md").read()
    return render_template("index.html", **data)

@app.route("/registration.html")
def registration():
    data = _data()
    data["registration"] = open("registration.md").read()
    return render_template("registration.html", **data)

@app.route("/organizers.html")
def organizers():
    data = _data()
    data["committee"] = site_data["committee"]["committee"]
    return render_template("organizers.html", **data)


@app.route("/speakers.html")
def speakers():
    data = _data()
    data["speakers"] = site_data["speakers"]["speakers"]
    return render_template("speakers.html", **data)


@app.route("/calls.html")
def calls():
    data = _data()
    data["calls"] = site_data["calls"]["calls"]
    for call in data["calls"]:
        call["bodytext"] = open(call["body"]).read()
    return render_template("calls.html", **data)


@app.route("/help.html")
def about():
    data = _data()
    data["FAQ"] = site_data["faq"]["FAQ"]
    return render_template("help.html", **data)


@app.route("/papers.html")
def papers():
    data = _data()
    data["papers"] = site_data["papers"]
    data["papers"].sort(key=lambda x: x["title"])
    return render_template("papers.html", **data)


@app.route("/calendar.html")
def schedule():
    data = _data()
    data["days"] = by_date
    return render_template("schedule.html", **data)


@app.route("/workshops.html")
def workshops():
    data = _data()
    data["workshops"] = [
        format_workshop(workshop) for workshop in site_data["workshops"]
    ]
    return render_template("workshops.html", **data)


@app.route("/tutorials.html")
def tutorials():
    data = _data()
    data["workshops"] = [
        format_workshop(tutorial) for tutorial in site_data["tutorials"]
    ]
    return render_template("workshops.html", **data)


@app.route("/panels.html")
def panels():
    data = _data()
    data["workshops"] = [
        format_workshop(panel) for panel in site_data["panels"]
    ]
    return render_template("workshops.html", **data)


@app.route("/hackathons.html")
def hackathons():
    data = _data()
    data["workshops"] = [
        format_workshop(hackathon) for hackathon in site_data["hackathons"]
    ]
    return render_template("workshops.html", **data)


@app.route("/genchal.html")
def genchal():
    data = _data()
    data["workshops"] = [
        format_workshop(genchal) for genchal in site_data["genchal"]
    ]
    return render_template("workshops.html", **data)


@app.route("/sponsors.html")
def sponsors():
    data = _data()
    data["goldsponsors"] = site_data["goldsponsors"]
    data["silversponsors"] = site_data["silversponsors"]
    data["bronzesponsors"] = site_data["bronzesponsors"]
    return render_template("sponsors.html", **data)


def extract_list_field(v, key):
    value = v.get(key, "")
    if isinstance(value, list):
        return value
    else:
        return value.split("|")


def format_paper(v):
    v["authors"] = extract_list_field(v, "authors")
    dt = datetime.strptime(v["start_time"], "%Y-%m-%dT%H:%M:%SZ")
    v["time"] = dt.strftime('%A %m/%d %H:%M EST')
    v["short_time"] = dt.strftime('%H:%M EST')
    v["title"] = v["title"].title()
    v["title"] = re.sub(r'Nlg', 'NLG', v["title"])
    return v

def format_workshop(v):
    v["organizers"] = extract_list_field(v, "authors")
    dt = datetime.strptime(v["start_time"], "%Y-%m-%dT%H:%M:%SZ")
    v["time"] = dt.strftime('%A %m/%d %H:%M EST')
    return v


# ITEM PAGES


@app.route("/poster_<poster>.html")
def poster(poster):
    uid = poster
    v = by_uid["papers"][uid]
    data = _data()
    data["paper"] = v
    return render_template("poster.html", **data)

# FRONT END SERVING


@app.route("/papers.json")
def paper_json():
    json = []
    for v in site_data["papers"]:
        json.append(v)
    json.sort(key=lambda x: x["title"])
    return jsonify(json)


@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)


@app.route("/serve_<path>.json")
def serve(path):
    # if path == 'tutorials':
    #     from IPython import embed
    #     embed()
    if isinstance(site_data[path], list):
        for idx, item in enumerate(site_data[path]):
            if isinstance(item, dict):
                site_data[path][idx] = {
                    ("None" if k == None else k): item[k]
                    for k in item
                }
        
    return jsonify(site_data[path])


# --------------- DRIVER CODE -------------------------->
# Code to turn it all static


@freezer.register_generator
def generator():
    for paper in site_data["papers"]:
        yield "poster", {"poster": str(paper["UID"])}

    for key in site_data:
        yield "serve", {"path": key}


def parse_arguments():
    parser = argparse.ArgumentParser(description="MiniConf Portal Command Line")

    parser.add_argument(
        "--build",
        action="store_true",
        default=False,
        help="Convert the site to static assets",
    )

    parser.add_argument(
        "-b",
        action="store_true",
        default=False,
        dest="build",
        help="Convert the site to static assets",
    )

    parser.add_argument("path", help="Pass the JSON data path and run the server")

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()

    site_data_path = args.path
    extra_files = main(site_data_path)

    if args.build:
        freezer.freeze()
    else:
        debug_val = False
        if os.getenv("FLASK_DEBUG") == "True":
            debug_val = True

        app.run(port=5000, debug=debug_val, extra_files=extra_files)
