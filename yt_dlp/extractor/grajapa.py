import re

from .common import InfoExtractor
from ..utils import (
    clean_html,
    extract_attributes,
    unified_timestamp,
    update_url,
    update_url_query,
    url_basename,
    url_or_none,
    urljoin,
)
from ..utils.traversal import find_element, require, traverse_obj


class GrajapaIE(InfoExtractor):
    IE_DESC = '週プレ グラジャパ！'

    _BASE_URL = 'https://www.grajapa.shueisha.co.jp'
    _ENDPOINT_RE = r'(?:index|interview|playall[1-4])'
    _M3U8_URL = 'https://safety.primestage.net/wpb-shupurenet/playlist.m3u8'
    _VALID_URL = rf'https?://(?:www\.)?grajapa\.shueisha\.co\.jp/plus/(?P<type>dvd|season_girl|special|weekly)(?:/archives)?/(?P<id>\d+)/?((?P<endpoint>{_ENDPOINT_RE})\.html)?'
    _TESTS = [{
        'url': 'https://www.grajapa.shueisha.co.jp/plus/special/archives/247/',
        'info_dict': {
            'id': '247',
            'title': '+ Special No.351 12 / 2025',
        },
        'playlist_count': 19,
    }, {
        'url': 'https://www.grajapa.shueisha.co.jp/plus/special/archives/238/playall4.html',
        'info_dict': {
            'id': '4X0vEDzMkbTx',
            'ext': 'mp4',
            'title': 'プレイオール Chapter 4',
            'alt_title': '礒部花凜',
            'artists': ['礒部花凜'],
            'categories': ['PLUS_SPECIAL'],
            'description': 'md5:5548986abf8d30ea411efdd69724cea1',
            'series': '「かりんとりっぷ」',
            'series_id': '238',
            'thumbnail': r're:https?://www\.grajapa\.shueisha\.co\.jp/.+',
            'timestamp': 1752548400,
            'upload_date': '20250715',
        },
    }, {
        'url': 'https://www.grajapa.shueisha.co.jp/plus/dvd/3642',
        'info_dict': {
            'id': 'SjqpNAaY4GSD',
            'ext': 'mp4',
            'title': '「かりんとりっぷ」礒部花凜 閲覧期限：2026年2月15日（日）23:59',
            'alt_title': '礒部花凜',
            'artists': ['礒部花凜'],
            'categories': ['PLUS_DVD'],
            'modified_date': '20250725',
            'modified_timestamp': 1753423850,
            'series': '2025年8月4日号No.30&31 特別付録DVD',
            'series_id': '3642',
            'thumbnail': r're:https?://www\.grajapa\.shueisha\.co\.jp/.+',
            'timestamp': 1753671600,
            'upload_date': '20250728',
        },
    }, {
        'url': 'https://www.grajapa.shueisha.co.jp/plus/dvd/3745',
        'info_dict': {
            'id': 'MeuGPgt3RFum',
            'ext': 'mp4',
            'title': 'プレミアムムービー',
            'alt_title': '花咲楓香 麻倉瑞季 白濱美兎',
            'artists': ['花咲楓香', '麻倉瑞季', '白濱美兎'],
            'categories': ['PLUS_DVD'],
            'modified_date': '20251121',
            'modified_timestamp': 1763694838,
            'series': '2025年11月24日号No.47 特別付録DVD',
            'series_id': '3745',
            'thumbnail': r're:https?://www\.grajapa\.shueisha\.co\.jp/.+',
            'timestamp': 1763953200,
            'upload_date': '20251124',
        },
    }, {
        'url': 'https://www.grajapa.shueisha.co.jp/plus/weekly/3627',
        'info_dict': {
            'id': 'LRQOUAVTCChs',
            'ext': 'mp4',
            'title': 'プレミアムムービー',
            'alt_title': '麻倉瑞季',
            'artists': ['麻倉瑞季'],
            'categories': ['PLUS_WEEKLY'],
            'modified_date': '20251217',
            'modified_timestamp': 1765939079,
            'series': '2025年7月7日',
            'series_id': '3627',
            'thumbnail': r're:https?://www\.grajapa\.shueisha\.co\.jp/.+',
            'timestamp': 1751857200,
            'upload_date': '20250707',
        },
    }, {
        'url': 'https://www.grajapa.shueisha.co.jp/plus/weekly/989',
        'info_dict': {
            'id': '989',
            'title': '大原優乃',
        },
        'playlist_count': 2,
    }]

    def _extract_fotmats(self, link_id):
        token = self._download_json(
            f'{self._BASE_URL}/api/movie/token/{link_id}', link_id)['token']
        formats = self._extract_m3u8_formats(update_url_query(
            self._M3U8_URL, {'id': link_id, 'tk': token}), link_id, 'mp4')

        return {
            'id': link_id,
            'formats': formats,
        }

    def _real_extract(self, url):
        video_type, video_id, endpoint = self._match_valid_url(url).group('type', 'id', 'endpoint')
        base_url = re.sub(
            rf'/(?:{self._ENDPOINT_RE})\.html', '', update_url(url, query='', fragment='')).rstrip('/')
        webpage = self._download_webpage(base_url, video_id)

        alt_title = traverse_obj(webpage, ((
            {find_element(cls='top-image-p')},
            {find_element(cls='c-model-profile__main-name')},
        ), {clean_html}, filter, any))
        metadata = {
            'alt_title': alt_title,
            'description': traverse_obj(webpage, (
                {find_element(cls='special-intro-copy')}, {clean_html}, filter)),
            'series_id': video_id,
            **traverse_obj(self._search_json(
                r'let\s+jsonString\s*=', webpage, 'JSON string', video_id, default={},
                contains_pattern=r"'(?s:{.+?})'", transform_source=lambda s: s[1:-1],
            ), {
                'artists': ('talents', ..., 'name', {clean_html}, filter, all, filter),
                'categories': ('category', {str}, all, filter),
                'series': ('title', {clean_html}),
                'thumbnail': ('thumbnail_url', {urljoin(base_url)}),
                'timestamp': ('DSP_START_DATE', {unified_timestamp}, {lambda x: x - 32400}),
            }),
        }

        entries = []
        if 'special' in video_type:
            playlist_title = traverse_obj(webpage, (
                {find_element(cls='special-intro-number')}, {clean_html}, filter))
            if not endpoint or endpoint == 'index':
                endpoints = [None, 'playall1', 'playall2', 'playall3', 'playall4', 'interview']
            else:
                endpoints = [endpoint]

            for endpoint in endpoints:
                webpage = self._download_webpage(
                    f'{base_url}/{endpoint}.html', video_id, f'Downloading {endpoint}') if endpoint else webpage
                imgs = re.finditer(r'<img[^>]+data-movie-link-id\s*=\s*(["\'])([\w-]{12})\1[^>]+>', webpage)
                for img in imgs:
                    attrs = extract_attributes(img.group(0))
                    if not endpoint and attrs['class'] != 'user-viewer-opening-movie':
                        break
                    entries.append({
                        **metadata,
                        **self._extract_fotmats(attrs['data-movie-link-id']),
                        **traverse_obj(attrs, {
                            'title': ('title', {clean_html}, filter),
                            'thumbnail': ('src', {urljoin(f'{base_url}/')}),
                        }),
                    })
        elif 'season_girl' in video_type:
            playlist_title = traverse_obj(webpage, (
                {find_element(cls='title')}, {clean_html}, filter))
            ga_map = self._search_json(
                r'let\s+ga_map\s*=', webpage, 'ga map', video_id, default={})
            for movie in self._search_json(
                r'let\s+paid_contents_movie\s*=', webpage, 'movie list',
                video_id, contains_pattern=r'\[(?s:.+?)\]', default=[],
            ):
                link_id = movie['linkId']
                entries.append({
                    'id': link_id,
                    'series': playlist_title,
                    'description': traverse_obj(webpage, (
                        {find_element(cls='description')}, {clean_html}, filter)),
                    **self._extract_fotmats(link_id),
                    **traverse_obj(webpage, ({find_element(cls='info')}, {
                        'title': ({find_element(cls='title')}, {clean_html}, filter),
                        'alt_title': ({find_element(cls='talent_name')}, {clean_html}, filter),
                    })),
                    **traverse_obj(ga_map, {
                        'thumbnail': ('thumbnail', {urljoin(base_url)}),
                        'timestamp': (link_id, {unified_timestamp}, {lambda x: x - 32400}),
                    }),
                })
        else:
            playlist_title = alt_title
            for movie in self._search_json(
                r'let\s+movie_list\s*=', webpage, 'movie list',
                video_id, contains_pattern=r'\[(?s:.+?)\]', default=[],
            ):
                link_id = traverse_obj(movie, (
                    'movie_script', {find_element(tag='iframe', html=True)},
                    {extract_attributes}, 'src', {url_or_none}, {url_basename}, {require('mv link ID')}))

                entries.append({
                    **metadata,
                    **self._extract_fotmats(link_id),
                    **traverse_obj(movie, {
                        'title': ('title', {clean_html}),
                        'modified_timestamp': ('updated_at', {unified_timestamp}, {lambda x: x - 32400}),
                    }),
                })

        if len(entries) == 1:
            return entries[0]
        else:
            return self.playlist_result(entries, video_id, playlist_title)
