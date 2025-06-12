import json

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    int_or_none,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import require, traverse_obj


class LiveJournalIE(InfoExtractor):
    IE_NAME = 'livejournal'

    _VALID_URL = r'https?://(?:[^./]+\.)?livejournal\.com/video/album/\d+\S*[?&]id=(?P<id>\d+)\b'
    _TESTS = [{
        'url': 'https://andrei-bt.livejournal.com/video/album/407/?mode=view&id=51272',
        'info_dict': {
            'id': '1263729',
            'ext': 'mp4',
            'title': 'Истребители против БПЛА.mp4',
            'display_id': '51272',
            'playlist_id': '407',
            'thumbnail': r're:https?://static\.eaglecdn\.com/.+\.jpg',
            'timestamp': 1561406715,
            'upload_date': '20190624',
            'uploader_id': 'andrei_bt',
        },
    }, {
        'url': 'https://dexter8262.livejournal.com/video/album/394/?mode=view&id=7538',
        'info_dict': {
            'id': '2617150',
            'ext': 'mp4',
            'title': 'центрополис.MOV',
            'display_id': '7538',
            'playlist_id': '394',
            'thumbnail': r're:https?://static\.eaglecdn\.com/.+\.jpg',
            'timestamp': 1749482104,
            'upload_date': '20250609',
            'uploader_id': 'dexter8262',
        },
    }, {
        'url': 'https://dexter8262.livejournal.com/3026.html',
        'md5': 'adaf018388572ced8a6f301ace49d4b2',
        'info_dict': {
            'id': '1263729',
            'ext': 'mp4',
            'title': 'Истребители против БПЛА',
            'upload_date': '20190624',
            'timestamp': 1561406715,
        },
    }]

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)

        record = self._search_json(
            r'Site\.page\s*=', webpage, 'page data', display_id)['video']['record']
        rambler_id, template_id = traverse_obj(record, {
            'rambler_id': ('storageid', {str_or_none}, {require('rambler player ID')}),
            'template_id': ('player_template_id', {str_or_none}, {require('player template ID')}),
        }).values()

        player_data = self._download_json(
            'https://api.vp.rambler.ru/api/v3/records/getPlayerData',
            display_id, headers={
                'Origin': 'https://andrei-bt.livejournal.com',
                'Referer': 'https://andrei-bt.livejournal.com/',
            }, query={
                'params': json.dumps({
                    'checkReferrerCount': True,
                    'id': rambler_id,
                    'playerTemplateId': template_id,
                    'referrer': url,
                }).encode(),
            })
        if not player_data.get('success'):
            raise ExtractorError(player_data['error']['type'], expected=True)
        playlist = player_data['result']['playList']

        formats = []
        for m3u8_url in traverse_obj(playlist, (
            ('directSource', 'source'), {url_or_none}, filter,
        )):
            formats.extend(self._extract_m3u8_formats(
                m3u8_url, rambler_id, 'mp4', fatal=False))
        self._remove_duplicate_formats(formats)

        return {
            'id': rambler_id,
            'display_id': display_id,
            'duration': traverse_obj(playlist, (
                'duration', {float_or_none(scale='1000')})),
            'formats': formats,
            **traverse_obj(record, {
                'title': ('name', {clean_html}),
                'age_limit': ('adult_content', {bool}, {lambda x: 18 if x else None}),
                'description': ('description', {clean_html}),
                'playlist_id': ('albumid', {str_or_none}),
                'thumbnail': ('screenshot', {url_or_none}),
                'timestamp': ('timecreate', {int_or_none}),
                'uploader_id': ('owner', {str}),
            }),
        }


class LiveJournalAlbumIE(InfoExtractor):
    IE_NAME = 'livejournal:album'

    _VALID_URL = r'https?://(?:[^./]+\.)?livejournal\.com/video/album/(?P<id>\d+)(?:[/?#]|$)'
    _TESTS = [{
        'url': 'https://dexter8262.livejournal.com/video/album/394/',
        'info_dict': {
            'id': '394',
            'title': 'DEFAULT',
        },
        'playlist_mincount': 28,
    }, {
        'url': 'https://andrei-bt.livejournal.com/video/album/407/',
        'info_dict': {
            'id': '407',
            'title': 'BTT',
        },
        'playlist_mincount': 260,
    }]

    def _real_extract(self, url):
        album_id = self._match_id(url)
        webpage = self._download_webpage(url, album_id)
        auth_token = self._search_json(
            r'var\s+p\s*=', webpage, 'auth token', album_id)['auth_token']
        user = self._hidden_inputs(webpage)['journal']

        payload = [{
            'jsonrpc': '2.0',
            'method': method,
            'id': index,
            'params': {
                'user': user,
                'auth_token': auth_token,
                **({'albumid': int(album_id)} if method == 'video.get_records' else {}),
            },
        } for index, method in enumerate(('video.get_records', 'video.get_albums'), 1)]
        api_resp = self._download_json(
            'https://www.livejournal.com/__api/', album_id, headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'text/plain',
            }, data=json.dumps(payload).encode())

        entries = [
            self.url_result(web_url, LiveJournalIE)
            for web_url in traverse_obj(api_resp, (
                ..., 'result', 'records', ..., 'webUrl', {url_or_none}))]

        return self.playlist_result(
            entries, album_id, traverse_obj(api_resp, (
                ..., 'result', 'albums', lambda _, v: v['id'] == int(album_id), 'name', {str.upper}, any)))
