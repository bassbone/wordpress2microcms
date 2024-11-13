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
        """
        環境変数から設定を読み込んで初期化
        """
        self.xml_file = os.getenv('WP_XML_FILE')
        self.domain = os.getenv('MICROCMS_DOMAIN')
        self.api_key = os.getenv('MICROCMS_API_KEY')
        
        # APIエンドポイントの構築
        self.api_endpoint = f"https://{self.domain}{os.getenv('MICROCMS_CONTENT_API_PATH')}"
        self.media_api_endpoint = f"https://{self.domain}{os.getenv('MICROCMS_MEDIA_API_PATH')}"
        
        # ヘッダーの設定
        self.headers = {
            'X-MICROCMS-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        self.image_cache = {}
        
        # 設定値の検証
        self._validate_config()

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
        
        # XMLファイルの存在確認
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
        
        posts = []
        for item in root.findall('.//item'):
            post_type = item.find('wp:post_type', namespaces)
            status = item.find('wp:status', namespaces)
            
            if post_type is not None and post_type.text == 'post' and status is not None and status.text == 'publish':
                post = {
                    'title': item.find('title').text,
                    'content': item.find('content:encoded', namespaces).text,
                    'date': item.find('wp:post_date', namespaces).text,
                    'categories': [cat.text for cat in item.findall('category[@domain="category"]')],
                    'tags': [tag.text for tag in item.findall('category[@domain="post_tag"]')]
                }
                posts.append(post)
        
        return posts

    def clean_content(self, content):
        """HTMLコンテンツのクリーニングと画像の処理"""
        if content:
            content = html.unescape(content)
        return content

    def upload_to_microcms(self, posts):
        """記事をmicroCMSにアップロード"""
        success_count = 0
        failed_count = 0
        
        for post in posts:
            try:
                data = {
                    'title': post['title'],
                    'body': self.clean_content(post['content']),
#                    'publishedAt': datetime.strptime(post['date'], '%Y-%m-%d %H:%M:%S').isoformat(),
#                    'categories': post['categories'],
#                    'tags': post['tags']
                }
                
                response = requests.post(
                    self.api_endpoint,
                    headers=self.headers,
                    json=data
                )
                
                if response.status_code == 201:
                    success_count += 1
                    print(f"記事をアップロードしました: {post['title']}")
                else:
                    failed_count += 1
                    print(f"記事のアップロードに失敗: {post['title']}")
                    print(f"エラー: {response.text}")
                
                time.sleep(1)
                
            except Exception as e:
                failed_count += 1
                print(f"記事のアップロードでエラー {post['title']}: {str(e)}")
        
        return success_count, failed_count

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
