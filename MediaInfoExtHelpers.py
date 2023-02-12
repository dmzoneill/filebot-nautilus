#!/usr/bin/python
# dave@fio.ie

from pprint import pprint
from gi.repository import Nautilus
import urllib.parse
import subprocess
import json
import re
import traceback
from pprint import pprint
import time


def ffprobe(details, file_info):
    filename = urllib.parse.unquote(file_info.get_uri()[7:])

    try:
        output = subprocess.check_output(
            [
                "ffprobe",
                "-hide_banner",
                "-loglevel",
                "error",
                "-print_format",
                "json",
                "-of",
                "json",
                "-show_entries",
                "format:stream",
                filename,
            ],
            stderr=subprocess.STDOUT,
            timeout=4,
        )
        results = json.loads(output.decode("utf-8"))

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

        # file_info.add_string_attribute("video_width", details["video_width"])
        # file_info.add_string_attribute("video_height", details["video_height"])
        # file_info.add_string_attribute(
        #    "video_codec_name", details["video_codec_name"])
        # file_info.add_string_attribute(
        #     "audio_codec_name", details["audio_codec_name"])
        # file_info.add_string_attribute(
        #     "audio_channels", details["audio_channels"])
    except Exception as e:
        print(filename)
        pprint(e)

    return details


def test_rename(file_info):
    filename = urllib.parse.unquote(file_info.get_uri()[7:])
    name_suggestion = ""

    try:
        print("test_rename")
        print(filename)

        # Define the command and arguments to be run
        command = 'filebot -rename -r "' + filename + '" -non-strict --action test'

        # Specify the timeout in seconds
        timeout = 7

        print("starting")
        # Run the command and arguments using Popen
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

        print("started")

        # Use a timer to keep track of the elapsed time
        start_time = time.time()

        # Wait for the process to complete or for the timeout to be exceeded
        while process.poll() is None:
            if time.time() - start_time > timeout:
                print("killing")
                process.kill()
                break

        # Get the output from the command
        output, error = process.communicate()

        # Decode the output and error to strings
        output = output.decode("utf-8")
        error = error.decode("utf-8")

        print(output)

        p = re.compile("\[TEST\] from \[(.*?)\] to \[(.*?)\]")
        result = p.search(output)
        if result is not None:
            pprint(result.group(1))
            pprint(result.group(2))

        if name_suggestion is not False:
            parts = result.group(2).split("/")
            name_suggestion = parts[len(parts) - 1]
        else:
            name_suggestion = ""

        # file_info.add_string_attribute("name_suggestion", str(name_suggestion))
    except Exception as e:
        pprint(e)

    return name_suggestion


def update_file_info(MediaInfoObj, filename):

    print(filename)

    if "details" not in MediaInfoObj.details[filename]:
        return

    pprint(MediaInfoObj.details[filename]["details"])

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


def run_task(MediaInfoObj, provider, handle, closure, file_info):
    try:
        filename = urllib.parse.unquote(file_info.get_uri()[7:])

        name_suggestion = test_rename(file_info)
        result = ffprobe({}, file_info)

        with MediaInfoObj.lock:
            MediaInfoObj.details[filename]["details"] = result
            MediaInfoObj.details[filename]["details"][
                "name_suggestion"
            ] = name_suggestion
            update_file_info(MediaInfoObj, filename)
            file_info.invalidate_extension_info()
            Nautilus.info_provider_update_complete_invoke(
                closure, provider, handle, Nautilus.OperationResult.COMPLETE
            )
    except Exception as e:
        pprint(e)
        traceback.print_exc()
