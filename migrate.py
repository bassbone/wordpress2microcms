import os
import xml.etree.ElementTree as ET
import requests
import html
import json
import time
from datetime import datetime
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
import mimetypes
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

class WPToMicroCMSMigration:
    def __init__(self):
        """環境変数から設定を読み込んで初期化"""
        self._load_config()
        self._validate_config()
        self.image_cache = {}

    def _load_config(self):
        """環境変数から設定を読み込む"""
        self.xml_file = os.getenv('WP_XML_FILE')
        self.domain = os.getenv('MICROCMS_DOMAIN')
        self.api_key = os.getenv('MICROCMS_API_KEY')
        self.api_endpoint = f"https://{self.domain}{os.getenv('MICROCMS_CONTENT_API_PATH')}"
        self.media_api_endpoint = f"https://{self.domain}{os.getenv('MICROCMS_MEDIA_API_PATH')}"
        self.headers = {
            'X-MICROCMS-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

    def _validate_config(self):
        """設定値の存在確認と検証"""
        required_vars = {
            'WP_XML_FILE': self.xml_file,
            'MICROCMS_DOMAIN': self.domain,
            'MICROCMS_API_KEY': self.api_key,
            'MICROCMS_CONTENT_API_PATH': os.getenv('MICROCMS_CONTENT_API_PATH'),
            'MICROCMS_MEDIA_API_PATH': os.getenv('MICROCMS_MEDIA_API_PATH')
        }
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"必要な環境変数が設定されていません: {', '.join(missing_vars)}")
        if not os.path.exists(self.xml_file):
            raise FileNotFoundError(f"指定されたXMLファイルが見つかりません: {self.xml_file}")

    def parse_wordpress_xml(self):
        """WordPressのXMLファイルを解析して記事データを取得"""
        tree = ET.parse(self.xml_file)
        root = tree.getroot()
        namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'wp': 'http://wordpress.org/export/1.2/',
            'excerpt': 'http://wordpress.org/export/1.2/excerpt/'
        }
        return [
            {
                'title': item.find('title').text,
                'content': item.find('content:encoded', namespaces).text,
                'date': item.find('wp:post_date', namespaces).text,
                'categories': [cat.text for cat in item.findall('category[@domain="category"]')],
                'tags': [tag.text for tag in item.findall('category[@domain="post_tag"]')]
            }
            for item in root.findall('.//item')
            if item.find('wp:post_type', namespaces).text == 'post' and item.find('wp:status', namespaces).text == 'publish'
        ]

    def clean_content(self, content):
        """HTMLコンテンツのクリーニングと画像の処理"""
        return html.unescape(content) if content else content

    def upload_to_microcms(self, posts):
        """記事をmicroCMSにアップロード"""
        success_count, failed_count = 0, 0
        for post in posts:
            if self._upload_post(post):
                success_count += 1
            else:
                failed_count += 1
            time.sleep(1)
        return success_count, failed_count

    def _upload_post(self, post):
        """単一の記事をmicroCMSにアップロード"""
        try:
            data = {
                'title': post['title'],
                'body': self.clean_content(post['content']),
                # 'publishedAt': datetime.strptime(post['date'], '%Y-%m-%d %H:%M:%S').isoformat(),
                # 'categories': post['categories'],
                # 'tags': post['tags']
            }
            response = requests.post(self.api_endpoint, headers=self.headers, json=data)
            if response.status_code == 201:
                print(f"記事をアップロードしました: {post['title']}")
                return True
            else:
                print(f"記事のアップロードに失敗: {post['title']}")
                print(f"エラー: {response.text}")
                return False
        except Exception as e:
            print(f"記事のアップロードでエラー {post['title']}: {str(e)}")
            return False

    def migrate(self):
        """移行プロセスの実行"""
        print("WordPress記事の解析を開始...")
        posts = self.parse_wordpress_xml()
        print(f"{len(posts)}件の記事を検出しました")
        print("microCMSへの移行を開始...")
        success, failed = self.upload_to_microcms(posts)
        print(f"\n移行完了:")
        print(f"成功: {success}件")
        print(f"失敗: {failed}件")
        print(f"処理した画像: {len(self.image_cache)}件")

def main():
    try:
        migrator = WPToMicroCMSMigration()
        migrator.migrate()
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
