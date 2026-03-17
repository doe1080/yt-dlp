import base64
import re

from .common import InfoExtractor
from ..networking import HEADRequest
from ..utils import (
    clean_html,
    encode_data_uri,
    int_or_none,
    multipart_encode,
    url_or_none,
    urlencode_postdata,
)
from ..utils.traversal import require, traverse_obj


class JoySoundCafeIE(InfoExtractor):
    IE_NAME = 'joysound:cafe'
    IE_DESC = 'ジョイサウンドカフェ'

    _BASE_URL = 'https://www.sound-cafe.jp/player'
    _VALID_URL = r'https?://www\.sound-cafe\.jp/songdetail/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.sound-cafe.jp/songdetail/424782',
        'info_dict': {
            'id': '424782',
            'ext': 'mp4',
            'title': 'Sincerely',
            'artists': ['TRUE'],
            'composers': 'count:1',
        },
    }, {
        'url': 'https://www.sound-cafe.jp/songdetail/612007',
        'info_dict': {
            'id': '612007',
            'ext': 'mp4',
            'title': 'Celestial',
            'artists': ['Ed Sheeran'],
            'composers': 'count:3',
        },
    }, {
        'url': 'https://www.sound-cafe.jp/songdetail/177905',
        'info_dict': {
            'id': '177905',
            'ext': 'mp4',
            'title': '深愛',
            'artists': ['水樹奈々'],
            'composers': 'count:1',
        },
    }]

    def _real_extract(self, url):
        audio_id = self._match_id(url)
        webpage = self._download_webpage(url, audio_id)
        hidden_inputs = self._hidden_inputs(webpage)
        song_number = traverse_obj(hidden_inputs, ('selSongNo', {str}))
        x_csrf_token = self._html_search_meta('_csrf', webpage, fatal=True)

        telop_info = self._download_json(
            f'{self._BASE_URL}/telopTitleInfo', audio_id, headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Csrf-Token': x_csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
            }, data=urlencode_postdata({'songNumber': song_number}))

        formats = []
        for guide in re.finditer(
            r'<input\b[^>]+\btype=(["\'])radio\1[^>]+\bid=(["\'])(?P<id>\w+)\2[^>]+value=(["\'])(?P<value>\d+)\4', webpage,
        ):
            format_id = guide.group('id')
            data, content_type = multipart_encode({
                'songNumber': song_number,
                'serviceType': guide.group('value'),
            })
            fme = self._download_json(
                f'{self._BASE_URL}/getFME', audio_id, headers={
                    'Accept': 'application/json',
                    'Content-Type': content_type,
                    'X-Csrf-Token': x_csrf_token,
                }, data=data)

            ogg = traverse_obj(fme, ('ogg', {str}, {require('Ogg Vorbis binary')}))
            ogg_bytes = base64.b64decode(ogg[30:] + ogg[:30])

            formats.append({
                'acodec': 'vorbis',
                'ext': 'ogg',
                'filesize': len(ogg_bytes),
                'format_id': format_id,
                'source_preference': -10 if format_id == 'vocal' else None,
                'url': encode_data_uri(ogg_bytes, 'audio/ogg'),
                'vcodec': 'none',
            })

        data, content_type = multipart_encode({
            'songNumber': song_number,
            'serviceType': '003000761',
        })
        contents_info = self._download_json(
            f'{self._BASE_URL}/contentsInfo', audio_id, headers={
                'Accept': 'application/json',
                'Content-Type': content_type,
                'X-Csrf-Token': x_csrf_token,
            }, data=data)
        movie_url = traverse_obj(contents_info, ('movie', 'mov1', {url_or_none}))
        urlh = self._request_webpage(
            HEADRequest(movie_url), audio_id, 'Checking filesize', fatal=False)
        filesize_approx = int_or_none(urlh.headers.get('Content-Length', None))

        formats.append({
            'acodec': 'none',
            'filesize_approx': filesize_approx,
            'format_id': 'movie',
            'height': 360,
            'url': movie_url,
            'vcodec': 'h264',
            'width': 640,
        })

        return {
            'id': song_number,
            'composers': traverse_obj(telop_info, (
                'composer', {clean_html}, {re.compile(r'[，&]').split},
                ..., {str.strip}, filter, all, filter)),
            'display_id': audio_id,
            'formats': formats,
            '_format_sort_fields': ('source_preference', ),
            **traverse_obj(hidden_inputs, {
                'title': ('songName', {clean_html}, filter),
                'artists': ('artistName', {clean_html}, filter, all, filter),
            }),
        }
