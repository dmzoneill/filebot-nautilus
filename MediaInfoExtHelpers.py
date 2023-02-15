#!/usr/bin/python
# dave@fio.ie

import logging
from pprint import pformat
import concurrent.futures
import urllib.parse
from os import listdir
from os.path import isfile, join
import subprocess
import json
import re
import time
import traceback
from pathlib import Path
import mimetypes


logging.basicConfig(filename="/tmp/VideoMetadataExtension.log", level=logging.DEBUG)


def get_output(command):
    logging.debug(command)

    # Specify the timeout in seconds
    timeout = 7

    logging.debug("get_output")
    # Run the command and arguments using Popen
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )

    logging.debug("started")

    # Use a timer to keep track of the elapsed time
    start_time = time.time()

    # Wait for the process to complete or for the timeout to be exceeded
    while process.poll() is None:
        if time.time() - start_time > timeout:
            logging.debug("killing")
            process.kill()
            break

    # Get the output from the command
    output, error = process.communicate()

    # Decode the output and error to strings
    output = output.decode("utf-8")
    error = error.decode("utf-8")

    # logging.debug(output)
    logging.debug("stopped")

    return output


def ffprobe(details, filename):
    logging.debug("get_ffprobe")
    logging.debug(filename)

    try:

        # Define the command and arguments to be run
        command = (
            'ffprobe -hide_banner -loglevel error -print_format json -of json -show_entries format:stream "'
            + filename
            + '"'
        )

        output = get_output(command)
        results = json.loads(output)

        audio_set = False
        video_set = False

        for stream in results["streams"]:
            if video_set is False:
                if stream["codec_type"] == "video":
                    for attribute in [
                        ["video_width", "coded_width", "width"],
                        ["video_height", "coded_height", "height"],
                        ["video_codec_name", "codec_name"],
                    ]:
                        if attribute[1] in stream:
                            video_set = True
                            details[attribute[0]] = str(stream[attribute[1]])

                        if len(attribute) == 3:
                            if attribute[2] in stream:
                                video_set = True
                                details[attribute[0]] = str(stream[attribute[2]])

            if audio_set is False:
                if stream["codec_type"] == "audio":
                    for attribute in [
                        ["audio_channels", "channels"],
                        ["audio_codec_name", "codec_name"],
                    ]:
                        if attribute[1] in stream:
                            details[attribute[0]] = str(stream[attribute[1]])
                            audio_set = True

                        if len(attribute) == 3:
                            if attribute[2] in stream:
                                details[attribute[0]] = str(stream[attribute[2]])
                                audio_set = True
    except Exception as e:
        logging.debug(filename)
        logging.debug(pformat(e))

    return details


def test_rename(filename):
    name_suggestion = ""

    try:
        logging.debug("test_rename")
        logging.debug(filename)

        # Define the command and arguments to be run
        command = 'filebot -rename -r "' + filename + '" -non-strict --action test'
        output = get_output(command)

        logging.debug(output)

        p = re.compile("\[TEST\] from \[(.*?)\] to \[(.*?)\]")
        result = p.search(output)
        if result is not None:
            logging.debug(result.group(1))
            logging.debug(result.group(2))

        if name_suggestion is not False:
            parts = result.group(2).split("/")
            name_suggestion = parts[len(parts) - 1]
        else:
            name_suggestion = ""

        # file_info.add_string_attribute("name_suggestion", str(name_suggestion))
    except Exception as e:
        logging.debug(e)

    return name_suggestion


def file_info_update(MediaInfoObj, filename):

    logging.debug("file_info_update: " + filename)

    if "details" not in MediaInfoObj.details[filename]:
        logging.debug("file_info_update: false update: " + filename)
        return

    logging.debug(pformat(MediaInfoObj.details[filename]["details"]))

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "name_suggestion",
        MediaInfoObj.details[filename]["details"]["name_suggestion"]
        if "name_suggestion" in MediaInfoObj.details[filename]["details"]
        else "",
    )

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "video_width",
        MediaInfoObj.details[filename]["details"]["video_width"]
        if "video_width" in MediaInfoObj.details[filename]["details"]
        else "",
    )

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "video_height",
        MediaInfoObj.details[filename]["details"]["video_height"]
        if "video_height" in MediaInfoObj.details[filename]["details"]
        else "",
    )

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "video_codec_name",
        MediaInfoObj.details[filename]["details"]["video_codec_name"]
        if "video_codec_name" in MediaInfoObj.details[filename]["details"]
        else "",
    )

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "audio_channels",
        MediaInfoObj.details[filename]["details"]["audio_channels"]
        if "audio_channels" in MediaInfoObj.details[filename]["details"]
        else "",
    )

    MediaInfoObj.details[filename]["file_info"].add_string_attribute(
        "audio_codec_name",
        MediaInfoObj.details[filename]["details"]["audio_codec_name"]
        if "audio_codec_name" in MediaInfoObj.details[filename]["details"]
        else "",
    )


def get_siblings(MediaInfoObj, filename):
    path = Path(filename)
    directory = path.parent.absolute()
    files = []

    videomimes = [
        "video/x-msvideo",
        "video/mpeg",
        "video/x-ms-wmv",
        "video/mp4",
        "video/x-flv",
        "video/x-matroska",
    ]

    for f in listdir(directory):
        the_file = join(directory, f)

        if the_file in MediaInfoObj.details.keys():
            continue

        if isfile(the_file) == False:
            continue

        mime = mimetypes.guess_type(the_file)[0]

        if mime in videomimes:
            files.append(the_file)

    return files


def run_detail_multi(MediaInfoObj, filename):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        try:
            for result in executor.map(
                run_detail, get_siblings(MediaInfoObj, filename)
            ):
                with MediaInfoObj.lock:
                    logging.debug("Updating : " + result["filename"])
                    MediaInfoObj.details[result["filename"]] = {}
                    MediaInfoObj.details[result["filename"]]["details"] = result
                    logging.debug(f"Task result: {result}")
        except:
            logging.debug(str(result.exception()))


def run_detail(filename):
    try:
        logging.debug("Multi run task: " + filename)
        print("Multi run task: " + filename)
        name_suggestion = test_rename(filename)
        result = ffprobe({}, filename)
        result["name_suggestion"] = name_suggestion
        result["filename"] = filename
        logging.debug(name_suggestion)
        logging.debug(result)
        logging.debug("Got name and details: " + filename)
        return result
    except Exception as e:
        logging.debug(pformat(e))
        traceback.print_exc()
        return {"filename": filename, "error": True}


def run_task(MediaInfoObj, filename):
    try:
        logging.debug("Run task: " + filename)

        run_detail_multi(MediaInfoObj, filename)

        # name_suggestion = test_rename(filename)
        # result = ffprobe({}, filename)

        # logging.debug("Got name and details: " + filename)

        # with MediaInfoObj.lock:
        #     logging.debug("Updating : " + filename)
        #     MediaInfoObj.details[filename] = {}
        #     MediaInfoObj.details[filename]["details"] = result
        #     MediaInfoObj.details[filename]["details"][
        #         "name_suggestion"
        #     ] = name_suggestion
    except Exception as e:
        logging.debug(pformat(e))
        traceback.print_exc()
