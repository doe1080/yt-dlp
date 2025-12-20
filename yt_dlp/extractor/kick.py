import datetime as dt
import functools
import re
import urllib.parse
import xml.etree.ElementTree as ET

from .common import InfoExtractor
from ..networking.exceptions import HTTPError
from ..utils import (
    ExtractorError,
    UserNotLive,
    clean_html,
    determine_ext,
    float_or_none,
    int_or_none,
    parse_iso8601,
    str_or_none,
    unified_timestamp,
    url_or_none,
)
from ..utils.traversal import find_element, traverse_obj


class KickBaseIE(InfoExtractor):
    @functools.cached_property
    def _api_headers(self):
        token = traverse_obj(
            self._get_cookies('https://kick.com/'),
            ('session_token', 'value', {urllib.parse.unquote}))
        return {'Authorization': f'Bearer {token}'} if token else {}

    def _call_api(self, path, display_id, note='Downloading API JSON', headers={}, **kwargs):
        return self._download_json(
            f'https://kick.com/api/{path}', display_id, note=note,
            headers={**self._api_headers, **headers}, impersonate=True, **kwargs)

    def _json_to_xml(self, messages, start_time):
        root = ET.Element('packet')
        for no, msg in enumerate(messages, 1):
            message = traverse_obj(msg, ('content', {clean_html}, filter))
            if msg['type'] == 'message' and message and not message.startswith('[emote:'):
                created_at = parse_iso8601(msg['created_at'])
                chat = ET.SubElement(root, 'chat', {
                    'user': msg['sender']['slug'],
                    'user_id': str(msg['user_id']),
                    'no': str(no),
                    'vpos': str((created_at - start_time) * 100),
                    'date': str(created_at),
                })
                chat.text = message

        xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"
        xml_body = ET.tostring(root, 'utf-8').decode('utf-8').replace('><', '>\n<')
        return xml_declaration + xml_body


class KickIE(KickBaseIE):
    IE_NAME = 'kick:live'
    _VALID_URL = r'https?://(?:www\.)?kick\.com/(?!(?:video|categories|search|auth)(?:[/?#]|$))(?P<id>[\w-]+)'
    _TESTS = [{
        'url': 'https://kick.com/buddha',
        'info_dict': {
            'id': '92722911-nopixel-40',
            'ext': 'mp4',
            'title': str,
            'description': str,
            'timestamp': int,
            'thumbnail': r're:https?://.+\.jpg',
            'categories': list,
            'upload_date': str,
            'channel': 'buddha',
            'channel_id': '32807',
            'uploader': 'Buddha',
            'uploader_id': '33057',
            'live_status': 'is_live',
            'concurrent_view_count': int,
            'release_timestamp': int,
            'age_limit': 18,
            'release_date': str,
        },
        'params': {'skip_download': 'livestream'},
        # 'skip': 'livestream',
    }, {
        'url': 'https://kick.com/xqc',
        'only_matching': True,
    }]

    @classmethod
    def suitable(cls, url):
        return False if (KickVODIE.suitable(url) or KickClipIE.suitable(url)) else super().suitable(url)

    def _real_extract(self, url):
        channel = self._match_id(url)
        response = self._call_api(f'v2/channels/{channel}', channel)
        if not traverse_obj(response, 'livestream', expected_type=dict):
            raise UserNotLive(video_id=channel)

        return {
            'channel': channel,
            'is_live': True,
            'formats': self._extract_m3u8_formats(response['playback_url'], channel, 'mp4', live=True),
            **traverse_obj(response, {
                'id': ('livestream', 'slug', {str}),
                'title': ('livestream', 'session_title', {str}),
                'description': ('user', 'bio', {str}),
                'channel_id': (('id', ('livestream', 'channel_id')), {int}, {str_or_none}, any),
                'uploader': (('name', ('user', 'username')), {str}, any),
                'uploader_id': (('user_id', ('user', 'id')), {int}, {str_or_none}, any),
                'timestamp': ('livestream', 'created_at', {unified_timestamp}),
                'release_timestamp': ('livestream', 'start_time', {unified_timestamp}),
                'thumbnail': ('livestream', 'thumbnail', 'url', {url_or_none}),
                'categories': ('recent_categories', ..., 'name', {str}),
                'concurrent_view_count': ('livestream', 'viewer_count', {int_or_none}),
                'age_limit': ('livestream', 'is_mature', {bool}, {lambda x: 18 if x else 0}),
            }),
        }


class KickVODIE(KickBaseIE):
    IE_NAME = 'kick:vod'
    _VALID_URL = r'https?://(?:www\.)?kick\.com/(?P<channel>[\w-]+)/videos/(?P<id>[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12})'
    _TESTS = [{
        'url': 'https://kick.com/xqc/videos/5a68dcd3-f248-4603-87a2-35c93f564ca6',
        'info_dict': {
            'id': '5a68dcd3-f248-4603-87a2-35c93f564ca6',
            'ext': 'mp4',
            'title': '😫LIVE😫CLCK😫DRAMA😫NEWS😫THINGS😫VIDEOS😫CLIPS😫GAMES😫LIVE😫QUICK😫CLICK IT😫DONT MISS IT😫BEST GAMER 2025😫TOO EZ😫',
            'age_limit': 18,
            'categories': ['Just Chatting'],
            'channel': 'xqc',
            'channel_id': '668',
            'duration': 45368,
            'live_status': 'was_live',
            'modified_date': str,
            'modified_timestamp': int,
            'release_date': '20251130',
            'release_timestamp': 1764536147,
            'thumbnail': r're:https?://.+\.webp',
            'timestamp': 1764536145,
            'upload_date': '20251130',
            'uploader': 'xQc',
            'uploader_id': '676',
            'view_count': int,
        },
        'expected_warnings': ['The extractor is attempting impersonation'],
    }]

    def _real_extract(self, url):
        channel, video_id = self._match_valid_url(url).group('channel', 'id')
        webpage = self._download_webpage(url, video_id, impersonate=True)
        video = traverse_obj(self._call_api(
            f'v2/channels/{channel}/videos', channel,
        ), (lambda _, v: v['video']['uuid'] == video_id, any))

        return {
            'id': video_id,
            'channel': channel,
            'formats': self._extract_m3u8_formats(video['source'], video_id, 'mp4'),
            'subtitles': self.extract_subtitles(video),
            'uploader': traverse_obj(webpage, ({find_element(id='channel-username')}, {clean_html}, filter)),
            **traverse_obj(video, {
                'title': ('session_title', {clean_html}),
                'age_limit': ('is_mature', {bool}, {lambda x: 18 if x else None}),
                'categories': ('categories', ..., 'name', {str}, filter),
                'duration': ('duration', {int_or_none(scale=1000)}),
                'is_live': ('is_live', {bool}),
                'live_status': ('is_live', {bool}, {lambda x: 'is_live' if x else 'was_live'}),
                'tags': ('tags', ..., {str}, filter),
                'thumbnails': ('thumbnail', 'srcset', {lambda x: [{
                    'height': int_or_none(height),
                    'url': url_or_none(url),
                    'width': int_or_none(width),
                } for url, height, width in re.findall(
                    r'(https?://[^,\s]+/(\d+)\.webp)\s+(\d+)w', x,
                )]}),
                'timestamp': ('start_time', {unified_timestamp}),
            }),
            **traverse_obj(video, ('channel', {
                'channel_id': ('id', {str_or_none}),
                'uploader_id': ('user_id', {str_or_none}),
            })),
            **traverse_obj(video, ('video', {
                'modified_timestamp': ('updated_at', {parse_iso8601}),
                'release_timestamp': ('created_at', {parse_iso8601}),
                'view_count': ('views', {int_or_none}),
            })),
        }

    def _get_subtitles(self, resp):
        channel_id = resp['channel_id']
        start_time = current_time = unified_timestamp(resp['start_time'])
        duration = float_or_none(resp['duration'], 1000)
        end_time = start_time + duration

        seen_ids, msgs = set(), []
        while current_time <= end_time:
            next_pos = current_time + 5
            query = dt.datetime.fromtimestamp(current_time, dt.timezone.utc).isoformat()
            try:
                pct = float_or_none(current_time - start_time, invscale=100, scale=duration, default=0) if duration else 0
                history = self._download_json(
                    f'https://web.kick.com/api/v1/chat/{channel_id}/history', channel_id,
                    f'Downloading {pct:.2f}% chat data', query={'start_time': query})['data']
                for msg in traverse_obj(history, (
                    'messages', lambda _, v: v['type'] == 'message',
                )):
                    msg_id = traverse_obj(msg, ('id', {str_or_none}))
                    if msg_id and msg_id not in seen_ids:
                        seen_ids.add(msg_id)
                        msgs.append(msg)

                if cursor := traverse_obj(history, (
                    'cursor', {float_or_none(scale=1_000_000)},
                )):
                    if cursor > current_time:
                        next_pos = cursor
                elif created_at := traverse_obj(history, (
                    'messages', ..., 'created_at', {parse_iso8601}, {max},
                )):
                    next_pos = max(next_pos, created_at + 5)
                current_time = next_pos
            except ExtractorError as e:
                if isinstance(e.cause, HTTPError) and e.cause.status == 400:
                    raise ExtractorError(self._parse_json(
                        e.cause.response.read().decode(), channel_id)['message'], expected=True)
        msgs.sort(key=lambda x: parse_iso8601(x['created_at']))

        return {
            'danmaku': [{
                'ext': 'xml',
                'data': self._json_to_xml(msgs, start_time),
            }],
        }


class KickClipIE(KickBaseIE):
    IE_NAME = 'kick:clips'
    _VALID_URL = r'https?://(?:www\.)?kick\.com/[\w-]+(?:/clips/|/?\?(?:[^#]+&)?clip=)(?P<id>clip_[\w-]+)'
    _TESTS = [{
        'url': 'https://kick.com/mxddy?clip=clip_01GYXVB5Y8PWAPWCWMSBCFB05X',
        'info_dict': {
            'id': 'clip_01GYXVB5Y8PWAPWCWMSBCFB05X',
            'ext': 'mp4',
            'title': 'Maddy detains Abd D:',
            'channel': 'mxddy',
            'channel_id': '133789',
            'uploader': 'AbdCreates',
            'uploader_id': '3309077',
            'thumbnail': r're:^https?://.*\.jpeg',
            'duration': 35,
            'timestamp': 1682481453,
            'upload_date': '20230426',
            'view_count': int,
            'like_count': int,
            'categories': ['VALORANT'],
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }, {
        'url': 'https://kick.com/destiny?clip=clip_01H9SKET879NE7N9RJRRDS98J3',
        'info_dict': {
            'id': 'clip_01H9SKET879NE7N9RJRRDS98J3',
            'title': 'W jews',
            'ext': 'mp4',
            'channel': 'destiny',
            'channel_id': '1772249',
            'uploader': 'punished_furry',
            'uploader_id': '2027722',
            'duration': 49.0,
            'upload_date': '20230908',
            'timestamp': 1694150180,
            'thumbnail': 'https://clips.kick.com/clips/j3/clip_01H9SKET879NE7N9RJRRDS98J3/thumbnail.png',
            'view_count': int,
            'like_count': int,
            'categories': ['Just Chatting'],
            'age_limit': 0,
        },
        'params': {'skip_download': 'm3u8'},
    }, {
        'url': 'https://kick.com/spreen/clips/clip_01J8RGZRKHXHXXKJEHGRM932A5',
        'info_dict': {
            'id': 'clip_01J8RGZRKHXHXXKJEHGRM932A5',
            'ext': 'mp4',
            'title': 'KLJASLDJKLJKASDLJKDAS',
            'channel': 'spreen',
            'channel_id': '5312671',
            'uploader': 'AnormalBarraBaja',
            'uploader_id': '26518262',
            'duration': 43.0,
            'upload_date': '20240927',
            'timestamp': 1727399987,
            'thumbnail': 'https://clips.kick.com/clips/f2/clip_01J8RGZRKHXHXXKJEHGRM932A5/thumbnail.webp',
            'view_count': int,
            'like_count': int,
            'categories': ['Minecraft'],
            'age_limit': 0,
        },
        'params': {'skip_download': 'm3u8'},
    }]

    def _real_extract(self, url):
        clip_id = self._match_id(url)
        clip = self._call_api(f'v2/clips/{clip_id}/play', clip_id)['clip']
        clip_url = clip['clip_url']

        if determine_ext(clip_url) == 'm3u8':
            formats = self._extract_m3u8_formats(clip_url, clip_id, 'mp4')
        else:
            formats = [{'url': clip_url}]

        return {
            'id': clip_id,
            'formats': formats,
            **traverse_obj(clip, {
                'title': ('title', {str}),
                'channel': ('channel', 'slug', {str}),
                'channel_id': ('channel', 'id', {int}, {str_or_none}),
                'uploader': ('creator', 'username', {str}),
                'uploader_id': ('creator', 'id', {int}, {str_or_none}),
                'thumbnail': ('thumbnail_url', {url_or_none}),
                'duration': ('duration', {float_or_none}),
                'categories': ('category', 'name', {str}, all),
                'timestamp': ('created_at', {parse_iso8601}),
                'view_count': ('views', {int_or_none}),
                'like_count': ('likes', {int_or_none}),
                'age_limit': ('is_mature', {bool}, {lambda x: 18 if x else 0}),
            }),
        }
