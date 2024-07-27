import json
from typing import Any
from dataclasses import dataclass
from pymediainfo import MediaInfo, Track as MediaInfoTrack

from ..utils.log import error
from ..utils.types import PathLike
from ..utils.env import communicate_stdout
from ..utils.download import get_executable
from ..utils.files import ensure_path_exists


@dataclass
class ProbedTrack:
    index: int
    relative_index: int
    codec: str
    codec_long: str
    type: str
    profile: str
    width: int
    height: int
    pix_fmt: str
    frame_rate: str
    bit_depth: int
    sample_fmt: str
    container_delay: int
    default: bool
    forced: bool
    title: str
    language: str
    raw: dict[str, Any]
    raw_tags: dict[str, Any] | None
    raw_disposition: dict[str, Any] | None
    mediainfo: MediaInfoTrack | None


@dataclass
class ContainerFormat:
    format_name: str
    format_long: str
    nb_streams: int
    size: int
    filename: str
    raw: dict[str, Any]


@dataclass
class ProbedMedia:
    tracks: list[ProbedTrack]
    container: ContainerFormat
    raw: dict[str, Any]

    @staticmethod
    def from_file(file: PathLike | list[PathLike], caller: Any | None = None) -> "ProbedMedia":
        file = ensure_path_exists(file, ProbedMedia if not caller else caller)
        ffprobe = get_executable("ffprobe")
        args = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", "-i", str(file.resolve())]
        returncode, output = communicate_stdout(args)
        if returncode != 0:
            print(output)
            raise error(f"Could not parse file '{file.name}' with ffprobe!", ProbedMedia)

        relative_indices = dict[str, int]()
        main_json = json.loads(output)

        format_json: dict = main_json.get("format")
        container = ContainerFormat(
            format_json.get("format_name", ""),
            format_json.get("format_long_name", ""),
            format_json.get("nb_streams", 0),
            format_json.get("size", 0),
            format_json.get("filename", str(file.resolve())),
            raw=format_json,
        )

        mediainfo = None if "matroska" not in container.format_name.lower() else MediaInfo.parse(file)

        tracks = list[ProbedTrack]()
        for stream in main_json.get("streams"):
            st: dict = stream
            index = st.get("index", 0)
            mediainfo_find = [tr for tr in mediainfo.tracks if int() == ()]
            track = None if not mediainfo_find else mediainfo_find[0]
            container_delay = getattr(track, "delay_relative_to_video", 0) if track else None

            codec_type = st.get("codec_type", "")
            disposition: dict = st.get("disposition")
            tags: dict | None = st.get("tags", None)

            relative = relative_indices.get(codec_type, 0)
            tracks.append(
                ProbedTrack(
                    index,
                    relative,
                    st.get("codec_name", ""),
                    st.get("codec_long_name", ""),
                    codec_type,
                    st.get("profile", ""),
                    st.get("width", 0),
                    st.get("height", 0),
                    st.get("pix_fmt", ""),
                    st.get("r_frame_rate", ""),
                    int(st.get("bits_per_raw_sample", 0)),
                    st.get("sample_fmt", ""),
                    int(container_delay) if container_delay else 0,
                    forced=disposition.get("forced", 0) == 1,
                    default=disposition.get("default", 0) == 1,
                    title=tags.get("title", "") if tags else "",
                    language=tags.get("language", "") if tags else "",
                    raw=st,
                    raw_tags=tags,
                    raw_disposition=disposition,
                    mediainfo=track,
                )
            )
            relative_indices[codec_type] = relative + 1

        return ProbedMedia(tracks, container, main_json)

    parse = from_file


def find_corresponding(tracks: list[MediaInfoTrack], probed: dict, index: int):
    for track in tracks:
        order = getattr(track, "streamorder", -1)
        order = -1 if order is None else int(order)
        if order != index:
            continue
        return track
