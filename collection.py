import requests
import json
import pandas as pd
from datetime import datetime
import time
import random
import urllib.parse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 获取用户输入的城市名称
def get_user_input():
    location = input("请输入要搜索的城市: ")
    return location

# Airbnb 数据爬取类
class AirbnbScraper:
    def __init__(self):
        # 设置重试策略，防止因网络问题导致爬取失败
        retry_strategy = Retry(
            total=3,  # 最大重试次数
            backoff_factor=1,  # 每次重试的等待时间倍数
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的 HTTP 状态码
        )

        # 初始化 HTTP 会话并设置重试机制
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # 设置默认的请求头
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    # 获取指定城市的所有房源信息
    def get_all_listings(self, location, check_in, check_out, adults=2, max_pages=20):
        all_listings = []  # 用于存储所有房源信息
        items_per_grid = 50  # 每页显示的房源数量

        # 遍历分页获取数据
        for offset in range(max_pages):
            print(f"\n正在获取第 {offset + 1} 页数据...")

            # 调用 get_listings 方法获取单页数据
            listings_df = self.get_listings(
                location=location,
                check_in=check_in,
                check_out=check_out,
                adults=adults,
                offset=offset * items_per_grid,
                items_per_grid=items_per_grid
            )

            # 如果没有数据则停止爬取
            if listings_df is None or listings_df.empty:
                print(f"第 {offset + 1} 页后无更多数据")
                break

            # 添加当前页数据到总集合中
            all_listings.append(listings_df)
            print(f"第 {offset + 1} 页找到 {len(listings_df)} 条数据")

            # 随机等待 3 到 5 秒，防止被目标网站屏蔽
            time.sleep(random.uniform(3, 5))

        # 如果没有任何房源数据，返回 None
        if not all_listings:
            return None

        # 将所有页数据合并为一个 DataFrame
        final_df = pd.concat(all_listings, ignore_index=True)
        print(f"\n共找到 {len(final_df)} 条房源数据")
        return final_df

    # 获取单页房源数据
    def get_listings(self, location, check_in=None, check_out=None, adults=2, offset=0, items_per_grid=50):
        try:
            base_url = "https://www.airbnb.com/api/v2/explore_tabs"

            # 构造 API 请求参数
            params = {
                '_format': 'for_explore_search_web',
                'currency': 'CNY',  # 使用人民币作为显示货币
                'locale': 'zh',  # 语言设为中文
                'query': location,  # 搜索的城市名称
                'adults': str(adults),
                'items_offset': str(offset),
                'items_per_grid': str(items_per_grid),
                'refinement_paths[]': '/homes',
                'key': 'd306zoyjsyarp7ifhu67rjxn52tv0t20',
            }

            # 如果指定了入住和退房时间，则加入请求参数
            if check_in:
                params['checkin'] = check_in
            if check_out:
                params['checkout'] = check_out

            # 更新请求头
            headers = self.base_headers.copy()
            headers.update({
                'referer': f'https://www.airbnb.com/s/{location}/homes',
            })

            print("正在发送请求到 Airbnb...")
            response = self.session.get(base_url, headers=headers, params=params)

            print(f"响应状态码: {response.status_code}")
            
            # 如果响应状态码不是 200，返回 None
            if response.status_code != 200:
                print(f"错误响应: {response.text[:500]}...")
                return None

            # 解析 JSON 数据
            data = response.json()
            return self._parse_listings(data)

        except Exception as e:
            print(f"请求出错: {str(e)}")
            return None

    # 解析返回的房源数据
    def _parse_listings(self, data):
        try:
            listings = []
            sections = data.get('explore_tabs', [{}])[0].get('sections', [])

            # 遍历所有的 sections 获取房源信息
            for section in sections:
                items = section.get('listings', [])
                for item in items:
                    listing = item.get('listing', {})
                    pricing_quote = item.get('pricing_quote', {})

                    # 如果房源信息为空，跳过
                    if not listing:
                        continue

                    # 解析房源价格
                    price = pricing_quote.get('price', {}).get('amount')

                    # 构造房源信息字典
                    parsed_listing = {
                        'name': listing.get('name'),
                        'address': listing.get('public_address', ''),
                        'price': price,
                        'rating': listing.get('avg_rating'),
                    }
                    listings.append(parsed_listing)

            # 将解析后的数据转换为 DataFrame
            if listings:
                return pd.DataFrame(listings)
            else:
                print("未找到房源信息")
                return pd.DataFrame()

        except Exception as e:
            print(f"解析房源数据出错: {e}")
            return pd.DataFrame()

    # 保存爬取的数据到 CSV 文件
    def save_to_csv(self, df, filename=None):
        if df is None or df.empty:
            print("没有数据可以保存")
            return

        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'airbnb_data_{timestamp}.csv'

        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"数据已保存到 {filename}")
        print(f"总记录数: {len(df)}")

# 主函数
def main():
    scraper = AirbnbScraper()

    # 获取用户输入的城市
    location = get_user_input()

    # 固定参数
    check_in = "2024-12-24"
    check_out = "2024-12-25"

    print(f"开始搜索 {location} 的房源...")
    listings_df = scraper.get_all_listings(location, check_in, check_out, adults=2, max_pages=1)

    if listings_df is not None and not listings_df.empty:
        print("爬取的房源数据:")
        print(listings_df.head())

        filename = f"{location}_airbnb_data.csv"
        scraper.save_to_csv(listings_df, filename)
    else:
        print("未找到任何房源")

if __name__ == "__main__":
    main()
