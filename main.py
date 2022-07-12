# pylint: disable=global-statement,redefined-outer-name
import argparse
import csv
from datetime import datetime
import glob
import json
import os

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

    for typ in ["papers", "workshops", "tutorials", "speakers", "social"]:
        by_uid[typ] = {}
        if typ == "papers":
           vals = site_data[typ].values()
        elif typ == "speakers":
            vals = site_data[typ]['speakers']
        elif typ in ["workshops", "tutorials"]:
            vals = [format_workshop(workshop) for workshop in site_data[typ]]
        else:
            vals = site_data[typ]
            
        for p in vals:
            by_uid[typ][p["UID"]] = p
            dt = datetime.strptime(p["start_time"], "%Y-%m-%dT%H:%M:%SZ")
            if dt.strftime('%A') not in by_date:
                by_date[dt.strftime('%A')] = {'name': dt.strftime('%A'), 'sessions': {}}
            if p["session"] not in by_date[dt.strftime('%A')]['sessions']:
                by_date[dt.strftime('%A')]['sessions'][p["session"]] = {'name': p["session"], 'time': dt, 'contents': []}
            if dt < by_date[dt.strftime('%A')]['sessions'][p["session"]]['time']:
                by_date[dt.strftime('%A')]['sessions'][p["session"]]['time'] = dt
            by_date[dt.strftime('%A')]['sessions'][p["session"]]['contents'].append(p)
            print(p["session"], len(by_date[dt.strftime('%A')]['sessions'][p["session"]]['contents']))
            
        for day in by_date.values():
            day['sessions'] = dict(sorted(day['sessions'].items(), key=lambda item: item[1]["time"]))
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
    data["papers"] = [x for x in site_data["papers"].values()]
    data["papers"].sort(key=lambda x: x["title"])
    return render_template("papers.html", **data)


@app.route("/calendar.html")
def schedule():
    data = _data()
    data["days"] = by_date
    print(data)
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
    data["tutorials"] = [
        format_workshop(tutorial) for tutorial in site_data["tutorials"]
    ]
    return render_template("tutorials.html", **data)


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
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "UID": v["UID"],
        "title": v["title"],
        "forum": v["UID"],
        "authors": list_fields["authors"],
        "abstract": v["abstract"],
        "session": v["session"],
        # links to external content per poster
        "slides": v["slides"] if "slides" in v else "",
        "poster": v["poster"] if "poster" in v else "", 
        "summary_video": v["summary_video"],
        "full_video": v["full_video"],
        "link": v["paper"] # link to paper
    }


def format_workshop(v):
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "UID": v["UID"],
        "start_time": v["start_time"],
        "session": v["session"],
        "title": v["title"],
        "organizers": list_fields["authors"],
        "abstract": v["abstract"],
    }


# ITEM PAGES


@app.route("/poster_<poster>.html")
def poster(poster):
    uid = poster
    v = by_uid["papers"][uid]
    data = _data()
    data["paper"] = format_paper(v)
    return render_template("poster.html", **data)

@app.route("/workshop_<workshop>.html")
def workshop(workshop):
    uid = workshop
    v = by_uid["workshops"][uid]
    data = _data()
    data["workshop"] = format_workshop(v)
    return render_template("workshop.html", **data)


# FRONT END SERVING


@app.route("/papers.json")
def paper_json():
    json = []
    for v in site_data["papers"].values():
        json.append(format_paper(v))
    json.sort(key=lambda x: x["title"])
    return jsonify(json)


@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)


@app.route("/serve_<path>.json")
def serve(path):
    return jsonify(site_data[path])


# --------------- DRIVER CODE -------------------------->
# Code to turn it all static


@freezer.register_generator
def generator():
    for paper in site_data["papers"]:
        yield "poster", {"poster": str(paper["UID"])}
    for workshop in site_data["workshops"]:
        yield "workshop", {"workshop": str(workshop["UID"])}

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
