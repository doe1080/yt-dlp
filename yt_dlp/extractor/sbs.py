import hashlib
import json
import re
import time

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    determine_ext,
    int_or_none,
    jwt_decode_hs256,
    parse_duration,
    parse_iso8601,
    str_or_none,
    url_or_none,
    urljoin,
)
from ..utils.traversal import traverse_obj


class SBSBaseIE(InfoExtractor):
    _API_KEY = '49a46461-b9eb-4904-b519-176c59c386ef'
    _AUTH_API = 'https://auth.sbs.com.au'
    _GEO_BYPASS = False
    _GEO_COUNTRIES = ['AU']
    _LOGIN_API_KEY = '74165a3a-0ae7-4d27-ac1a-e71e81062a89'
    _NETRC_MACHINE = 'sbs'

    _LANGUAGES = ('ar', 'en', 'hi', 'ko', 'vi', 'zh-Hans', 'zh-Hant')
    _LANGUAGES_RE = '|'.join(map(re.escape, _LANGUAGES))
    _BASE_URL_RE = rf'https?://(?:www\.)?sbs\.com\.au/ondemand(?:/(?:{_LANGUAGES_RE}))?'

    _access_token = None
    _refresh_token = None

    @staticmethod
    def _cache_key(username):
        return hashlib.sha256(username.encode()).hexdigest()

    def _is_jwt_expired(self, token):
        return jwt_decode_hs256(token)['exp'] - time.time() < 300

    def _refresh_access_token(self):
        if not self._refresh_token:
            return False

        self._set_cookie('.sbs.com.au', 'auth.refresh-token', self._refresh_token)

        refresh_data = self._download_json(
            f'{self._AUTH_API}/refresh', None,
            'Refreshing access token', headers={
                'Content-Type': 'application/json',
                'X-Api-Key': self._API_KEY,
            }, data=json.dumps({
                'deviceName': '',
                'refreshTokenInBody': True,
            }, separators=(',', ':')).encode(), expected_status=400)

        access_token = traverse_obj(refresh_data, ('accessToken', {str}, filter))
        if not access_token:
            self._access_token = self._refresh_token = None
            if username := self._get_login_info()[0]:
                self.cache.store(self._NETRC_MACHINE, self._cache_key(username), None)
            return False

        self._access_token = access_token
        self._refresh_token = traverse_obj(refresh_data, (
            'refreshToken', {str}, filter)) or self._refresh_token
        if username := self._get_login_info()[0]:
            self.cache.store(
                self._NETRC_MACHINE, self._cache_key(username), self._refresh_token)

        return True

    def _perform_login(self, username, password):
        cache_key = self._cache_key(username)
        if not self._refresh_token:
            self._refresh_token = self.cache.load(self._NETRC_MACHINE, cache_key)

        if self._refresh_token and self._refresh_access_token():
            return

        login_data = self._download_json(
            f'{self._AUTH_API}/login', None,
            'Logging in', headers={
                'Content-Type': 'application/json',
                'X-Api-Key': self._LOGIN_API_KEY,
            }, data=json.dumps({
                'deviceName': '',
                'email': username,
                'password': password,
                'refreshTokenInBody': True,
            }, separators=(',', ':')).encode(), expected_status=401)

        err_msg = traverse_obj(login_data, ('detail', {clean_html}, filter))
        access_token = traverse_obj(login_data, ('accessToken', {str}, filter))
        if err_msg or not access_token:
            raise ExtractorError(
                f'Unable to log in: {err_msg or "Invalid username or password"}', expected=True)

        self._access_token = access_token
        self._refresh_token = traverse_obj(login_data, ('refreshToken', {str}, filter))
        self.cache.store(self._NETRC_MACHINE, cache_key, self._refresh_token)

    def _get_auth_headers(self):
        if not self._access_token:
            return {}

        if (
            self._is_jwt_expired(self._access_token)
            and not self._refresh_access_token()
        ):
            self.report_warning(
                'Unable to refresh access token: retrying with credentials')
            self._perform_login(*self._get_login_info())

        return {'Authorization': f'Bearer {self._access_token}'}


class SBSIE(SBSBaseIE):
    IE_NAME = 'sbs'
    IE_DESC = 'Special Broadcasting Service'

    _CLASSIFICATION_AGE_LIMITS = {
        'G': 0,
        'PG': 15,
        'M': 15,
        'MA15+': 15,
    }
    _VALID_URL = rf'{SBSBaseIE._BASE_URL_RE}/watch/(?P<id>[0-9]+)'
    # _VALID_URL = r'''(?x)
    #     https?://(?:www\.)?sbs\.com\.au/(?:
    #         ondemand(?:
    #             /video/(?:single/)?|
    #             /(?:movie|tv-program)/[^/]+/|
    #             /(?:tv|news)-series/(?:[^/]+/){3}|
    #             .*?\bplay=|/watch/
    #         )|news/(?:embeds/)?video/
    #     )(?P<id>[0-9]+)'''
    # _EMBED_REGEX = [r'''(?x)]
    #         (?:
    #             <meta\s+property="og:video"\s+content=|
    #             <iframe[^>]+?src=
    #         )
    #         (["\'])(?P<url>https?://(?:www\.)?sbs\.com\.au/ondemand/video/.+?)\1''']
    _TESTS = [{
        # tv-series
        # https://www.sbs.com.au/ondemand/tv-series/hudson-and-rex/season-1/hudson-and-rex-s1-ep1/2219837507654
        'url': 'https://www.sbs.com.au/ondemand/watch/2219837507654',
        'info_dict': {
            'id': '2219837507654',
            'ext': 'mp4',
            'title': 'The Hunt',
            'age_limit': 15,
            'alt_title': 'Hudson & Rex S1 Ep1 - The Hunt',
            'cast': 'count:7',
            'description': 'md5:20f9ac5dbd39e5bfcb07c923e19abf1e',
            'duration': 2510,
            'episode': 'The Hunt',
            'episode_id': 'hudson-and-rex-s1-ep1',
            'episode_number': 1,
            'genres': 'count:1',
            'release_year': 2019,
            'season': 'Season 1',
            'season_id': 'season-1',
            'season_number': 1,
            'series': 'Hudson & Rex',
            'series_id': 'hudson-and-rex',
            'thumbnail': r're:https?://.+',
            'timestamp': 1756656000,
            'upload_date': '20250831',
        },
    }, {
        # tv-program
        # https://www.sbs.com.au/ondemand/tv-program/finding-dawn/313084995698
        'url': 'https://www.sbs.com.au/ondemand/watch/313084995698',
        'info_dict': {
            'id': '313084995698',
            'ext': 'mp4',
            'title': 'Finding Dawn',
            'age_limit': 15,
            'alt_title': 'Finding Dawn',
            'cast': 'count:1',
            'channel': 'NITV',
            'description': 'md5:6e3915b3992dffb237cdd3ab1d0f4453',
            'duration': 4407,
            'genres': 'count:2',
            'release_year': 2007,
            'series': 'Finding Dawn',
            'series_id': 'finding-dawn',
            'thumbnail': r're:https?://.+',
            'timestamp': 1787574300,
            'upload_date': '20260824',
        },
    }, {
        # tv-program, livestream
        # https://www.sbs.com.au/ondemand/tv-program/sbs-live-stream/1726824003663
        'url': 'https://www.sbs.com.au/ondemand/watch/1726824003663',
        'info_dict': {
            'id': '1726824003663',
            'ext': 'mp4',
            'title': str,
            'alt_title': 'SBS - Live Stream',
            'channel': 'SBS',
            'description': str,
            'live_status': 'is_live',
            'series': 'SBS - Live Stream',
            'series_id': 'sbs-live-stream',
            'thumbnail': r're:https?://.+',
            'timestamp': 1524405600,
            'upload_date': '20180422',
        },
        'params': {'skip_download': 'Livestream'},
    }, {
        # movie
        # https://www.sbs.com.au/ondemand/movie/all-quiet-on-the-western-front/1698704451971
        'url': 'https://www.sbs.com.au/ondemand/watch/1698704451971',
        'info_dict': {
            'id': '1698704451971',
            'ext': 'mp4',
            'title': 'All Quiet on the Western Front',
            'age_limit': 15,
            'alt_title': 'All Quiet On The Western Front',
            'cast': 'count:11',
            'channel': 'SBS World Movies',
            'description': 'md5:3d28bcd9b0cd06d18bf4c0730b23a69e',
            'duration': 9004,
            'genres': 'count:1',
            'release_year': 1979,
            'series': 'All Quiet on the Western Front',
            'series_id': 'all-quiet-on-the-western-front',
            'thumbnail': r're:https?://.+',
            'timestamp': 1667480400,
            'upload_date': '20221103',
        },
    }, {
        # news-series
        # https://www.sbs.com.au/ondemand/news-series/dateline/dateline-2022/dateline-s2022-ep26/2072245827515
        'url': 'https://www.sbs.com.au/ondemand/watch/2072245827515',
        'info_dict': {
            'id': '2072245827515',
            'ext': 'mp4',
            'title': 'Senior Sex And The City',
            'alt_title': 'Dateline S2022 Ep26 - Senior Sex And The City',
            'description': 'md5:893fc970110c5985ab186a0f05d00e09',
            'duration': 1686,
            'episode': 'Senior Sex And The City',
            'episode_id': 'dateline-s2022-ep26',
            'episode_number': 26,
            'genres': 'count:4',
            'season': 'Dateline 2022',
            'season_id': 'dateline-2022',
            'season_number': 2022,
            'series': 'Dateline',
            'series_id': 'dateline',
            'thumbnail': r're:https?://.+',
            'timestamp': 1664861400,
            'upload_date': '20221004',
        },
    }, {
        # sports-series
        # https://www.sbs.com.au/ondemand/sports-series/la-vuelta-2026/la-vuelta-2026-full-stages/la-vuelta-2026-full-stages-s2026-ep1/2507021379927
        'url': 'https://www.sbs.com.au/ondemand/watch/2507021379927',
        'info_dict': {
            'id': '2507021379927',
            'ext': 'mp4',
            'title': 'Stage 1',
            'alt_title': 'La Vuelta 2026: Full Stages: Stage 1',
            'description': 'md5:4967bb9097d20549a3b379a7e0b1da02',
            'duration': 12719,
            'episode': 'Stage 1',
            'episode_id': 'la-vuelta-2026-full-stages-s2026-ep1',
            'episode_number': 1,
            'genres': 'count:2',
            'season': 'Full Stages',
            'season_id': 'la-vuelta-2026-full-stages',
            'season_number': 2026,
            'series': 'La Vuelta a Espana 2026',
            'series_id': 'la-vuelta-2026',
            'thumbnail': r're:https?://.+',
            'timestamp': 1787422800,
            'upload_date': '20260822',
        },
    }]

    def _extract_thumbnails(self, item):
        thumbnails = []
        for image in traverse_obj(item, (
            'images', lambda _, v: v['category'].endswith('|KEY_ART') and v['id'],
        )):
            ratio, width, height, _ = image['category'].split('|')
            if ratio != '16:9':
                continue
            thumbnails.append({
                'url': urljoin('https://image.pr.sbsod.com/', image['id']),
                'width': int_or_none(width),
                'height': int_or_none(height),
            })

        return thumbnails

    def _real_extract(self, url):
        video_id = self._match_id(url)
        network = self._download_json(
            'https://www.sbs.com.au/api/v3/network',
            video_id, 'Checking geo-restriction', fatal=False)
        country_code = traverse_obj(network, (
            'get', 'response', 'country_code', {str}, filter))
        if country_code and country_code not in ('AU', 'CX', 'NF'):
            self.raise_geo_restricted(
                countries=self._GEO_COUNTRIES, metadata_available=True)

        stream = self._download_json(
            f'https://playback.pr.sbsod.com/stream/{video_id}', video_id,
            headers={
                'Content-Type': 'application/json',
                **self._get_auth_headers(),
            }, data=json.dumps({
                'deviceClass': 'web',
                'streamOptions': {'audio': 'demuxed'},
                'streamProviders': ['HLS'],
            }).encode())

        entity_type = traverse_obj(stream, ('entityType', {str.upper}, filter))
        path = {
            'MOVIE': 'movies',
            'NEWS_EPISODE': 'news-series',
            'NEWS_PROGRAM': 'news-programs',
            'SPORTS_EPISODE': 'sports-series',
            'SPORTS_PROGRAM': 'sports-programs',
            'TV_EPISODE': 'tv-series',
            'TV_PROGRAM': 'tv-programs',
        }.get(entity_type)
        if not path:
            raise ExtractorError(f'Unsupported entity type: {entity_type}')

        if entity_type in ('NEWS_EPISODE', 'SPORTS_EPISODE', 'TV_EPISODE'):
            entity_id = traverse_obj(
                stream, ('externalIDs', 'seriesID', {str}, filter))
        else:
            entity_id = traverse_obj(stream, ('slug', {str}, filter))
        entity = self._download_json(
            f'https://catalogue.pr.sbsod.com/{path}/{entity_id}',
            video_id, headers={
                'X-Api-Key': self._API_KEY,
                **self._get_auth_headers(),
            })

        episode = traverse_obj(entity, (
            'seasons', ..., 'episodes',
            lambda _, v: str_or_none(v['mpxMediaID']) == video_id, any, {dict}))
        season = traverse_obj(entity, (
            'seasons', lambda _, v: v['seasonNumber'] == episode['seasonNumber'], any, {dict}))

        m3u8_url = traverse_obj(stream, ('streamProviders', ..., 'url', {url_or_none}, any))
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(m3u8_url, video_id, 'mp4')

        for caption in traverse_obj(stream, (
            'streamProviders', ..., 'textTracks', lambda _, v: url_or_none(v['url']),
        )):
            lang = traverse_obj(caption, ('lang', {clean_html}, filter)) or 'und'
            if caption.get('type') == 'FORCED_NARRATIVE':
                lang += '-forced'

            caption_url = caption['url']
            subtitles.setdefault(lang, []).append({
                'ext': determine_ext(caption_url),
                'name': traverse_obj(caption, ('name', {clean_html}, filter)),
                'url': caption_url,
            })

        return {
            'id': video_id,
            'formats': formats,
            'is_live': traverse_obj(stream, ('streamType', {str}, filter)) == 'live',
            'subtitles': subtitles,
            'thumbnails': self._extract_thumbnails(episode) or self._extract_thumbnails(entity),
            **traverse_obj(stream, {
                'title': ('title', {clean_html}, filter),
                'alt_title': ('cdpTitle', {clean_html}, filter),
                'duration': ('duration', {parse_duration}),
                'timestamp': ('availability', 'start', {parse_iso8601}),
            }),
            **traverse_obj(entity, {
                'age_limit': ('classificationID', {self._CLASSIFICATION_AGE_LIMITS.get}),
                'cast': ('casts', ..., 'name', {clean_html}, filter, all, filter),
                'channel': ('channels', ..., {clean_html}, filter, any),
                'description': ('description', {clean_html}, filter),
                'genres': ('genres', ..., {clean_html}, filter, all, filter),
                'release_year': ('releaseYear', {int_or_none}),
                'series': ('title', {clean_html}, filter),
                'series_id': ('slug', {str}, filter),
            }),
            **traverse_obj(episode, {
                'episode': ('title', {clean_html}, filter),
                'episode_id': ('slug', {str}, filter),
                'episode_number': ('episodeNumber', {int_or_none}),
                'release_year': ('releaseYear', {int_or_none}),
            }),
            **traverse_obj(season, {
                'season': ('title', {clean_html}, filter),
                'season_id': ('slug', {str}, filter),
                'season_number': ('seasonNumber', {int_or_none}),
            }),
        }
