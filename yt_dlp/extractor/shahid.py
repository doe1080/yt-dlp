import datetime as dt
import json
import math
import re

from .aws import AWSIE
from ..networking.exceptions import HTTPError
from ..utils import (
    ExtractorError,
    InAdvancePagedList,
    clean_html,
    int_or_none,
    parse_duration,
    parse_iso8601,
    str_or_none,
    update_url,
    url_or_none,
    urlencode_postdata,
)
from ..utils.traversal import require, traverse_obj


class ShahidBaseIE(AWSIE):
    _AWS_PROXY_HOST = 'api2.shahid.net'
    _AWS_API_KEY = '2RRtuMHx95aNI1Kvtn2rChEuwsCogUd4samGPjLh'
    _VALID_URL_BASE = r'https?://shahid\.mbc\.net/[a-z]{2}/'

    def _handle_error(self, e):
        fail_data = self._parse_json(
            e.cause.response.read().decode('utf-8'), None, fatal=False)
        if fail_data:
            faults = fail_data.get('faults', [])
            faults_message = ', '.join([clean_html(fault['userMessage']) for fault in faults if fault.get('userMessage')])
            if faults_message:
                raise ExtractorError(faults_message, expected=True)

    def _call_api(self, path, video_id, request=None):
        query = {}
        if request:
            query['request'] = json.dumps(request)
        try:
            return self._aws_execute_api({
                'uri': '/proxy/v2/' + path,
                'access_key': 'AKIAI6X4TYCIXM2B7MUQ',
                'secret_key': '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',
            }, video_id, query)
        except ExtractorError as e:
            if isinstance(e.cause, HTTPError):
                self._handle_error(e)
            raise


class ShahidIE(ShahidBaseIE):
    _NETRC_MACHINE = 'shahid'
    _VALID_URL = ShahidBaseIE._VALID_URL_BASE + r'(?:serie|show|movie)s/[^/]+/(?P<type>episode|clip|movie)-(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://shahid.mbc.net/ar/shows/%D9%85%D8%AA%D8%AD%D9%81-%D8%A7%D9%84%D8%AF%D8%AD%D9%8A%D8%AD-%D8%A7%D9%84%D9%85%D9%88%D8%B3%D9%85-1-%D9%83%D9%84%D9%8A%D8%A8-1/clip-816924',
        'info_dict': {
            'id': '816924',
            'ext': 'mp4',
            'title': 'متحف الدحيح الموسم 1 كليب 1',
            'timestamp': 1602806400,
            'upload_date': '20201016',
            'description': 'برومو',
            'duration': 22,
            'categories': ['كوميديا'],
        },
        'params': {
            # m3u8 download
            'skip_download': True,
        },
    }, {
        'url': 'https://shahid.mbc.net/ar/movies/%D8%A7%D9%84%D9%82%D9%86%D8%A7%D8%B5%D8%A9/movie-151746',
        'only_matching': True,
    }, {
        # shahid plus subscriber only
        'url': 'https://shahid.mbc.net/ar/series/%D9%85%D8%B1%D8%A7%D9%8A%D8%A7-2011-%D8%A7%D9%84%D9%85%D9%88%D8%B3%D9%85-1-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-1/episode-90511',
        'only_matching': True,
    }, {
        'url': 'https://shahid.mbc.net/en/shows/Ramez-Fi-Al-Shallal-season-1-episode-1/episode-359319',
        'only_matching': True,
    }]

    def _perform_login(self, username, password):
        try:
            user_data = self._download_json(
                'https://shahid.mbc.net/wd/service/users/login',
                None, 'Logging in', data=json.dumps({
                    'email': username,
                    'password': password,
                    'basic': 'false',
                }).encode(), headers={
                    'Content-Type': 'application/json; charset=UTF-8',
                })['user']
        except ExtractorError as e:
            if isinstance(e.cause, HTTPError):
                self._handle_error(e)
            raise

        self._download_webpage(
            'https://shahid.mbc.net/populateContext',
            None, 'Populate Context', data=urlencode_postdata({
                'firstName': user_data['firstName'],
                'lastName': user_data['lastName'],
                'userName': user_data['email'],
                'csg_user_name': user_data['email'],
                'subscriberId': user_data['id'],
                'sessionId': user_data['sessionId'],
            }))

    def _real_extract(self, url):
        page_type, video_id = self._match_valid_url(url).groups()
        if page_type == 'clip':
            page_type = 'episode'

        playout = self._call_api(
            'playout/new/url/' + video_id, video_id)['playout']

        if not self.get_param('allow_unplayable_formats') and playout.get('drm'):
            self.report_drm(video_id)

        formats = self._extract_m3u8_formats(re.sub(
            # https://docs.aws.amazon.com/mediapackage/latest/ug/manifest-filtering.html
            r'aws\.manifestfilter=[\w:;,-]+&?',
            '', playout['url']), video_id, 'mp4')

        # video = self._call_api(
        #     'product/id', video_id, {
        #         'id': video_id,
        #         'productType': 'ASSET',
        #         'productSubType': page_type.upper()
        #     })['productModel']

        response = self._download_json(
            f'http://api.shahid.net/api/v1_1/{page_type}/{video_id}',
            video_id, 'Downloading video JSON', query={
                'apiKey': 'sh@hid0nlin3',
                'hash': 'b2wMCTHpSmyxGqQjJFOycRmLSex+BpTK/ooxy6vHaqs=',
            })
        data = response.get('data', {})
        error = data.get('error')
        if error:
            raise ExtractorError(
                '{} returned error: {}'.format(self.IE_NAME, '\n'.join(error.values())),
                expected=True)

        video = data[page_type]
        title = video['title']
        categories = [
            category['name']
            for category in video.get('genres', []) if 'name' in category]

        return {
            'id': video_id,
            'title': title,
            'description': video.get('description'),
            'thumbnail': video.get('thumbnailUrl'),
            'duration': int_or_none(video.get('duration')),
            'timestamp': parse_iso8601(video.get('referenceDate')),
            'categories': categories,
            'series': video.get('showTitle') or video.get('showName'),
            'season': video.get('seasonTitle'),
            'season_number': int_or_none(video.get('seasonNumber')),
            'season_id': str_or_none(video.get('seasonId')),
            'episode_number': int_or_none(video.get('number')),
            'episode_id': video_id,
            'formats': formats,
        }


class ShahidShowIE(ShahidBaseIE):
    _VALID_URL = ShahidBaseIE._VALID_URL_BASE + r'(?:show|serie)s/[^/]+/(?:show|series)-(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://shahid.mbc.net/ar/shows/%D8%B1%D8%A7%D9%85%D8%B2-%D9%82%D8%B1%D8%B4-%D8%A7%D9%84%D8%A8%D8%AD%D8%B1/show-79187',
        'info_dict': {
            'id': '79187',
            'title': 'رامز قرش البحر',
            'description': 'md5:c88fa7e0f02b0abd39d417aee0d046ff',
        },
        'playlist_mincount': 32,
    }, {
        'url': 'https://shahid.mbc.net/ar/series/How-to-live-Longer-(The-Big-Think)/series-291861',
        'only_matching': True,
    }]
    _PAGE_SIZE = 30

    def _real_extract(self, url):
        show_id = self._match_id(url)

        product = self._call_api(
            'playableAsset', show_id, {'showId': show_id})['productModel']
        playlist = product['playlist']
        playlist_id = playlist['id']
        show = product.get('show', {})

        def page_func(page_num):
            playlist = self._call_api(
                'product/playlist', show_id, {
                    'playListId': playlist_id,
                    'pageNumber': page_num,
                    'pageSize': 30,
                    'sorts': [{
                        'order': 'DESC',
                        'type': 'SORTDATE',
                    }],
                })
            for product in playlist.get('productList', {}).get('products', []):
                product_url = product.get('productUrl', []).get('url')
                if not product_url:
                    continue
                yield self.url_result(
                    product_url, 'Shahid',
                    str_or_none(product.get('id')),
                    product.get('title'))

        entries = InAdvancePagedList(
            page_func,
            math.ceil(playlist['count'] / self._PAGE_SIZE),
            self._PAGE_SIZE)

        return self.playlist_result(
            entries, show_id, show.get('title'), show.get('description'))


class ShahidLiveIE(ShahidBaseIE):
    _API_BASE = 'https://api3.shahid.net/proxy/v2.1'
    _VALID_URL = r'https?://shahid\.mbc\.net/(?P<lang>[^/]+)/livestream/[^/]+/livechannel-(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://shahid.mbc.net/en/livestream/MBC1/livechannel-387238',
        'info_dict': {
            'id': '387238',
            'ext': 'mp4',
            'title': str,
            'channel': 'MBC1',
            'channel_id': '387238',
            'description': 'md5:082811f682fe90e56198e009fef7ad8d',
            'duration': 3240,
            'episode': 'Episode 3',
            'episode_id': '968991',
            'episode_number': 3,
            'genres': 'count:2',
            'live_status': 'is_live',
            'release_year': 2022,
            'season': 'Season 1',
            'season_id': '966248',
            'season_number': 1,
            'series_id': '966247',
            'thumbnail': r're:https?://.+',
            'timestamp': 1790269500,
            'upload_date': '20260924',
        },
        'params': {'skip_download': 'Livestream'},
    }]

    def _real_extract(self, url):
        video_id, lang = self._match_valid_url(url).group('id', 'lang')
        playout = self._download_json(
            f'{self._API_BASE}/playout/new/url/{video_id}',
            video_id, query={'outputParameter': 'vmap'})['playout']
        if playout.get('drm'):
            self.report_drm(video_id)

        m3u8_url = traverse_obj(playout, ('url', {url_or_none}, {require('m3u8 URL')}))
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(m3u8_url, video_id, 'mp4')

        page_request = json.dumps({'pageAlias': 'livestream', 'profileFolder': 'WW'}).encode()
        page = self._download_json(
            f'{self._API_BASE}/editorial/page', video_id, query={'request': page_request})
        carousel_id = traverse_obj(page, (
            'carousels', ..., 'id', {str}, filter, any, {require('carousel ID')}))

        carousel_request = json.dumps({'id': carousel_id}).encode()
        carousel = self._download_json(
            f'{self._API_BASE}/editorial/carousel',
            video_id, query={'request': carousel_request})
        product = traverse_obj(carousel, (
            'editorialItems', lambda _, v: str_or_none(v['item']['id']) == video_id,
            'item', {dict}, any))

        now = dt.datetime.now().astimezone()

        def epg_time(**kwargs):
            return now.replace(**kwargs).astimezone(
                dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

        epg = self._download_json(
            f'{self._API_BASE}/shahid-epg-api/', video_id, query={
                'csvChannelIds': video_id,
                'language': lang,
                'from': epg_time(hour=0, minute=0, second=0, microsecond=0),
                'to': epg_time(hour=23, minute=59, second=59, microsecond=999000),
            })

        epg_now = traverse_obj(epg, ('serverCurrentTimestampUTC', {parse_iso8601}))
        program = traverse_obj(epg, ('items', ..., 'items', lambda _, v: (
            parse_iso8601(v.get('actualFrom')) <= epg_now < parse_iso8601(v.get('actualTo'))
        ), {dict}, any))
        if traverse_obj(program, ('emptySlot', {bool})):
            program = {}

        return {
            'id': video_id,
            'is_live': True,
            'formats': formats,
            'subtitles': subtitles,
            **traverse_obj(product, {
                'title': ('title', {clean_html}, filter),
                'channel': ('title', {clean_html}, filter),
                'channel_id': ('id', {str_or_none}),
                'description': ('description', {clean_html}, filter),
                'thumbnail': ('thumbnailImage', {url_or_none}, {update_url(query=None)}),
            }),
            **traverse_obj(program, {
                'title': ('title', {clean_html}, filter),
                'description': ('description', {clean_html}, filter),
                'duration': ('duration', {str}, {lambda x: parse_duration(x.rsplit(':', 1)[0])}),
                'episode_id': ('productId', {str_or_none}),
                'episode_number': ('episodeNumber', {int_or_none}),
                'genres': ('genres', ..., {clean_html}, filter, all, filter),
                'release_year': ('productionYear', {int_or_none}),
                'season_id': ('seasonId', {str_or_none}),
                'season_number': ('seasonNumber', {int_or_none}),
                'series_id': ('showId', {str_or_none}),
                'thumbnail': ('productPoster', {url_or_none}, {update_url(query=None)}),
                'timestamp': ('actualFrom', {parse_iso8601}),
            }),
        }
