import json

from .common import InfoExtractor
from .rambler import RamblerBaseIE
from ..utils import (
    clean_html,
    int_or_none,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import require, traverse_obj


class LiveJournalIE(RamblerBaseIE):
    IE_NAME = 'livejournal'

    _VALID_URL = r'https?://(?:[^./]+\.)?livejournal\.com/video/album/\d+\S*[?&]id=(?P<id>\d+)\b'
    _TESTS = [{
        'url': 'https://andrei-bt.livejournal.com/video/album/407/?mode=view&id=51272',
        'info_dict': {
            'id': 'record::cd3a90df-5a7d-41f5-843d-e85df46a9749',
            'ext': 'mp4',
            'title': 'Истребители против БПЛА.mp4',
            'display_id': '51272',
            'duration': 69.34,
            'playlist_id': '407',
            'thumbnail': r're:https?://static\.eaglecdn\.com/.+\.jpg',
            'timestamp': 1561406715,
            'upload_date': '20190624',
            'uploader': 'andrei_bt',
            'uploader_id': '18425682',
        },
    }, {
        'url': 'https://dexter8262.livejournal.com/video/album/394/?mode=view&id=7538',
        'info_dict': {
            'id': 'record::ed386b24-dc20-4f78-94c4-4e21473d09f9',
            'ext': 'mp4',
            'title': 'центрополис.MOV',
            'display_id': '7538',
            'duration': 17.0,
            'playlist_id': '394',
            'thumbnail': r're:https?://static\.eaglecdn\.com/.+\.jpg',
            'timestamp': 1749482104,
            'upload_date': '20250609',
            'uploader': 'dexter8262',
            'uploader_id': '96101788',
        },
    }]

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)

        record = self._search_json(
            r'Site\.page\s*=', webpage, 'page data', display_id)['video']['record']
        rambler_id = traverse_obj(record, (
            'storageid', {str_or_none}, {require('rambler ID')}))

        return {
            **self._extract_from_rambler_api(rambler_id, url),
            'display_id': display_id,
            'uploader_id': self._hidden_inputs(webpage)['journalId'],
            **traverse_obj(record, {
                'title': ('name', {clean_html}),
                'age_limit': ('adult_content', {bool}, {lambda x: 18 if x else None}),
                'description': ('description', {clean_html}),
                'playlist_id': ('albumid', {str_or_none}),
                'thumbnail': ('screenshot', {url_or_none}),
                'timestamp': ('timecreate', {int_or_none}),
                'uploader': ('owner', {str}),
            }),
        }


class LiveJournalAlbumIE(InfoExtractor):
    IE_NAME = 'livejournal:album'

    _VALID_URL = r'https?://(?:[^./]+\.)?livejournal\.com/video/album/(?P<id>\d+)(?!.*[?&]id=)(?:[/?#]|$)'
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
                'auth_token': auth_token,
                'user': user,
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
