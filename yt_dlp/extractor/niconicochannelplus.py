import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    int_or_none,
    str_or_none,
    unified_timestamp,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class NiconicoChannelPlusBaseIE(InfoExtractor):
    def _call_api(self, domain, path, item_id, *args, **kwargs):
        return self._download_json(
            f'https://api.{domain}/fc/{path}', item_id, *args, **kwargs)


class NiconicoChannelPlusIE(NiconicoChannelPlusBaseIE):
    IE_NAME = 'niconicochannelplus'
    IE_DESC = 'ニコニコチャンネルプラス'

    _DOMAINS = {
        '2': 'nfc-site01.com',
        '7': 'nfc-site02.com',
        '8': 'monogatari-sp.com',
        '57': 'hololive-fc.com',
        '58': 'tokinosora-fc.com',
        '59': 'pizzaradio.jp',
        '95': 'ado-dokidokihimitsukichi-daigakuimo.com',
        '100': 'rnqq.jp',
        '104': 'asato-yuya.com',
        '128': 'canan8181.com',
        '131': 'minami-hamabe.net',
        '158': 'nfc-site03.com',
        '159': 'nfc-site04.com',
        '160': 'nfc-site05.com',
        '161': 'nfc-site06.com',
        # '162': 'dazbee-fc.com',
        '173': 'keisuke-ueda.jp',
        '184': 'takahashifumiya.com',
        '204': 'gs-ch.com',
        '211': 'p-jinriki-fc.com',
        '212': 'ryogomatsumaru.com',
        '226': 'yamingfc.net',
        '242': 'banbanzai-fc.com',
        '243': 'kemomimirefle.net',
        '244': 'hyakuta.com',
        '279': 'rehacq-mattari.com',
        '281': 'salon-de-horizon.jp',
        '292': 'tominaga-yuya.com',
        '316': 'sakuraknights.com',
        '321': 'quizknock-schole.com',
        '322': 'styleparty-fc.jp',
        '323': 'itomiku-fc.jp',
        # '327': 'serina-official.com',
        # '336': 'ahnbohyun-fc.com',
        '350': 'malice-kibana.com',
        '386': 'sweetpowerfc.com',
        '389': 'toz-fc.com',
        '411': 'sae-okazaki.com',
        '418': 'pedrotv.tokyo',
        '429': 'nanase-fc.com',
        '448': 'tymstorage.jp',
        '450': 'yumeki-fc.com',
        '464': 'yoshino-za.com',
        '524': 'tenshi-nano.com',
        '525': 'yoji-iwase.com',
        '551': 'suzuka-ouji-officialfc.com',
        '552': 'kyoten-waku-officialfc.com',
        '555': 'kamiofuju.com',
        '558': 'sheeta-d01.com',
        '559': 'sheeta-d02.com',
        '560': 'sheeta-d03.com',
        '561': 'sheeta-d04.com',
        '563': 'sheeta-d06.com',
        '564': 'sheeta-d07.com',
        '565': 'sheeta-d08.com',
        '566': 'sheeta-d09.com',
        '567': 'sheeta-d10.com',
        '569': 'rabbitxparty.com',
        '618': 'nightmare-salon.com',
        '632': 'kawahara-no.jp',
        '650': 'maziyabacity.com',
        '662': 'shibuya-abemas.com',
        '664': 'ldh-live-square.com',
        '739': 'kabashimahikari.com',
        '796': 'yoko-minamino.com',
        '801': 'sheeta-demo1.com',
        '802': 'sheeta-demo2.com',
        '803': 'sheeta-demo3.com',
        '834': 'fudanjuku-plus.com',
        '982': 'harananoka.com',
    }
    _PARENT_DOMAINS = {
        '1': 'nicochannel.jp',
        '294': 'qlover.jp',
        '353': 'audee-membership.jp',
        '812': 'bayfm-channel.jp',
        '869': 'sheeta.jp',
    }
    _DOMAIN_RE = '|'.join(map(re.escape, {
        *_DOMAINS.values(),
        *_PARENT_DOMAINS.values(),
    }))
    _VALID_URL = rf'https?://(?P<domain>{_DOMAIN_RE})(?:/(?P<channel_id>[\w.-]+))?/(?:audio|live|video)/(?P<id>sm\w+)'
    _TESTS = [{
        # Free video; ニコニコチャンネルプラス
        'url': 'https://nicochannel.jp/shio-show-time/video/sm5R2ihENahSqntsFKv65q7U',
        'info_dict': {
            'id': 'sm5R2ihENahSqntsFKv65q7U',
            'ext': 'mp4',
            'title': '希水しおのシォータイムが始まります！',
            'description': 'md5:3c7183f2f4e641520dca2fc2c6b8cce2',
            'duration': 137,
            'channel': '希水しおのシォータイム',
            'channel_id': 'shio-show-time',
            'channel_url': 'https://nicochannel.jp/shio-show-time',
            'comment_count': int,
            'live_status': 'not_live',
            'thumbnail': r're:https?://nicochannel\.jp/.+',
            'timestamp': 1657274400,
            'upload_date': '20220708',
            'uploader': 'ニコニコチャンネルプラス',
            'uploader_id': '153',
            'view_count': int,
        },
    }, {
        # Age-restricted video; ニコニコチャンネルプラス
        'url': 'https://nicochannel.jp/testman/video/smmPbdGrhe8hZjX6pba9WY5P',
        'info_dict': {
            'id': 'smmPbdGrhe8hZjX6pba9WY5P',
            'ext': 'mp4',
            'title': 'WHONE-331_test_20240607',
            'age_limit': 18,
            'channel': '本番チャンネルプラステストマン',
            'channel_id': 'testman',
            'channel_url': 'https://nicochannel.jp/testman',
            'comment_count': int,
            'description': 'あいうえおtest',
            'duration': 15,
            'live_status': 'not_live',
            'thumbnail': r're:https?://nicochannel\.jp/.+',
            'timestamp': 1717740600,
            'upload_date': '20240607',
            'uploader': 'ニコニコチャンネルプラス',
            'uploader_id': '56',
            'view_count': int,
        },
    }, {
        # Free audio; Podcasts Membership
        'url': 'https://audee-membership.jp/coco-hayashi/audio/smE6PTsrPocjnRxKim6SCbKi',
        'info_dict': {
            'id': 'smE6PTsrPocjnRxKim6SCbKi',
            'ext': 'mp4',
            'title': '【#0】林鼓子のメゾン・ド・ココ プレオープン🎉🎉🎉',
            'channel': '林鼓子のメゾンド・ココ',
            'channel_id': 'coco-hayashi',
            'channel_url': 'https://audee-membership.jp/coco-hayashi',
            'comment_count': int,
            'description': 'md5:83c786fc36f539e8638c16ecc8c2d787',
            'duration': 405,
            'live_status': 'not_live',
            'tags': 'count:1',
            'thumbnail': r're:https?://audee-membership\.jp/.+',
            'timestamp': 1767358800,
            'upload_date': '20260102',
            'uploader': 'Podcasts Membership',
            'uploader_id': '994',
            'view_count': int,
        },
    }, {
        # Partially free video; QloveR
        'url': 'https://qlover.jp/hitomiho/video/smPX9ZCRLpTwCHeptnNXhR74',
        'info_dict': {
            'id': 'smPX9ZCRLpTwCHeptnNXhR74',
            'ext': 'mp4',
            'title': '【前半無料】岡咲美保・関根瞳の24時のシンデレラ 放送直前生配信',
            'channel': '岡咲美保・関根瞳の24時のシンデレラ',
            'channel_id': 'hitomiho',
            'channel_url': 'https://qlover.jp/hitomiho',
            'comment_count': int,
            'description': 'md5:b713e5d807c3fa020b429dc2dfe32741',
            'duration': 1890,
            'live_status': 'was_live',
            'release_date': '20250822',
            'release_timestamp': 1755860400,
            'section_end': 1890,
            'section_start': 0,
            'tags': 'count:1',
            'thumbnail': r're:https?://qlover\.jp/.+',
            'timestamp': 1755502430,
            'upload_date': '20250818',
            'uploader': 'QloveR',
            'uploader_id': '892',
            'view_count': int,
        },
    }, {
        # Partially free video, multiple free sections; ニコニコチャンネルプラス
        'url': 'https://nicochannel.jp/testman/video/smfEDXh4B4UEoqEDi6tjfFVc',
        'info_dict': {
            'id': 'smfEDXh4B4UEoqEDi6tjfFVc',
        },
        'playlist_count': 2,
    }]

    def _real_extract(self, url):
        domain, channel_id, video_id = self._match_valid_url(url).group('domain', 'channel_id', 'id')
        origin = channel_url = f'https://{domain}'

        if domain in self._PARENT_DOMAINS.values():
            channels = self._download_json(
                f'https://api.{domain}/fc/content_providers/channels', video_id)
            fc_site_id = traverse_obj(channels, (
                'data', 'content_providers',
                lambda _, v: v['domain'] in url, 'id', {str_or_none}, any))
            channel_url = f'{origin}/{channel_id}'
        else:
            fc_site_id = self._download_json(
                f'{origin}/site/settings.json', video_id)['fanclub_site_id']

        video_page = self._download_json(
            f'https://api.{domain}/fc/video_pages/{video_id}',
            video_id, 'Fetching video page', 'Unable to fetch video page info',
            headers={'Fc_site_id': fc_site_id, 'Fc_use_device': 'null'},
        )['data']['video_page']
        free_periods = traverse_obj(video_page, ('video_free_periods', ..., {
            'section_end': ('elapsed_ended_time', {int_or_none}),
            'section_start': ('elapsed_started_time', {int_or_none}),
        }))

        user_info = self._download_json(
            f'https://api.{domain}/fc/fanclub_sites/{fc_site_id}/user_info',
            fc_site_id, 'Fetching user info', 'Unable to fetch user info',
            fatal=False, headers={
                'Content-Type': 'application/json',
            }, data=b'null')
        plan_id = traverse_obj(user_info, (
            'data', 'fanclub_site', 'fanclub_specific_profile',
            'active_fanclub_membership', 'fanclub_billing_plan', 'id', {str_or_none}))

        target_id = traverse_obj(video_page, ('video_delivery_target', 'id', {int_or_none}))
        if target_id == 1:
            if plan_id:
                free_periods = []
            elif not free_periods:
                self.raise_login_required()
        elif target_id == 3:
            if traverse_obj(video_page, (
                'video_custom_targets',
                lambda _, v: str_or_none(v['fanclub_billing_plan']['id']) == plan_id,
                'video_custom_delivery_target', 'id', {int_or_none}, any,
            )) != 1:
                self.raise_login_required()
        elif target_id != 2:
            raise ExtractorError(f'Unknown target id: {target_id}', expected=True)

        if video_page.get('live_finished_at'):
            live_status = 'was_live'
        elif video_page['type'] == 'vod':
            live_status = 'not_live'
        else:
            live_status = 'is_live' if video_page.get('live_started_at') else 'is_upcoming'

        scheduled_time = traverse_obj(video_page, ('live_scheduled_start_at', {str}))
        release_timestamp = unified_timestamp(scheduled_time)
        if live_status == 'is_upcoming':
            self.raise_no_formats(
                f'This livestream is scheduled to start at {scheduled_time}', expected=True)
            return {
                'id': video_id,
                'release_timestamp': release_timestamp,
            }

        page_base_info = self._download_json(
            f'https://api.{domain}/fc/fanclub_sites/{fc_site_id}/page_base_info',
            fc_site_id, 'Fetching page base info', 'Unable to fetch page base info', fatal=False)

        if m3u8_url := traverse_obj(video_page, (
            'video_stream', 'authenticated_url', {url_or_none},
        )):
            session_ids = self._download_json(
                f'https://api.{domain}/fc/video_pages/{video_id}/session_ids', video_id,
                'Fetching session id', 'Unable to fetch session id', headers={
                    'Content-Type': 'application/json',
                    'Fc_use_device': 'null',
                    'Origin': origin,
                }, data=b'{}')
            session_id = traverse_obj(session_ids, ('data', 'session_id', {str}))
            m3u8_url = m3u8_url.format(session_id=session_id)
        else:
            content_access = self._download_json(
                f'https://api.{domain}/fc/video_pages/{video_id}/content_access', video_id,
                'Fetching content access', 'Unable to fetch content access', headers={
                    'Fc_site_id': fc_site_id,
                    'Fc_use_device': 'null',
                    'Origin': origin,
                })
            m3u8_url = traverse_obj(content_access, ('data', 'resource', {url_or_none}))

        formats = self._extract_m3u8_formats(m3u8_url, video_id, 'mp4')
        for f in formats:
            f['downloader_options'] = {'ffmpeg_args': ['-seekable', '0']}

        metadata = {
            'id': video_id,
            'age_limit': traverse_obj(user_info, (
                'data', 'fanclub_site', 'content_provider', 'age_limit', {int_or_none})),
            'channel_id': channel_id or domain,
            'channel_url': channel_url,
            'formats': formats,
            'live_status': live_status,
            'release_timestamp': release_timestamp,
            'uploader_id': fc_site_id,
            **traverse_obj(video_page, {
                'title': ('title', {clean_html}),
                'description': ('description', {clean_html}, filter),
                'duration': ('active_video_filename', 'length', {int_or_none}),
                'tags': ('video_tags', ..., 'tag', {clean_html}, filter),
                'thumbnail': ('thumbnail_url', {url_or_none}),
                'timestamp': ('released_at', {unified_timestamp}),
            }),
            **traverse_obj(video_page, ('video_aggregate_info', {
                'comment_count': ('number_of_comments', {int_or_none}),
                'view_count': ('total_views', {int_or_none}),
            })),
            **traverse_obj(page_base_info, ('data', 'fanclub_site', {
                'channel': ('fanclub_site_name', {clean_html}, filter),
                'uploader': ('fanclub_group', 'primary_content_provider', 'fanclub_site_name', {clean_html}, filter),
            })),
        }

        if not free_periods:
            return metadata
        if len(free_periods) == 1:
            return {**free_periods[0], **metadata}

        return self.playlist_result([{
            **free_period,
            **metadata,
            'id': f'{video_id}-{n}',
        } for n, free_period in enumerate(free_periods, 1)], video_id)
