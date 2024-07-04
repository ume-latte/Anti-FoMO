import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# 設置 Spotify API 的客戶端憑證
client_id = 'your_client_id'
client_secret = 'your_client_secret'

# 初始化 Spotify 的客戶端憑證管理器
client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# 搜尋歌曲
def search_track(query):
    results = sp.search(q=query, limit=1)
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        print(f"Found track: {track['name']} by {track['artists'][0]['name']}")
    else:
        print("No tracks found.")

# 主程式
if __name__ == '__main__':
    # 輸入要搜尋的歌曲名稱
    search_query = input("Enter a song name: ")
    search_track(search_query)
