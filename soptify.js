const SpotifyWebApi = require("spotify-web-api-node");

class Spotify {

    constructor() {
        // 初始化與 Spotify 的連接
        this.api = new SpotifyWebApi({
            clientId: process.env.SPOTIFY_CLIENT_ID,
            clientSecret: process.env.SPOTIFY_CLIENT_SECRET,
            redirectUri: process.env.SPOTIFY_CALLBACK
        });

        // 創建登入 URL，以便能夠獲取主要設備連接到揚聲器的各種權限
        const scopes = ["playlist-read-private", "playlist-modify", "playlist-modify-private"];
        const authorizeUrl = this.api.createAuthorizeURL(scopes, "default-state");
        console.log(`需要授權。請訪問 ${authorizeUrl}`);
    }

    isAuthTokenValid() {
        if (this.auth == undefined || this.auth.expires_at == undefined) {
            return false;
        }
        else if (this.auth.expires_at < new Date()) {
            return false;
        }
        return true;
    }

    async initialized() {
        const playlists = [];

        const limit = 50;
        let offset = -limit;
        let total = 0;

        // 下載已登錄用戶在 Spotify 上的所有播放列表並存儲在變量 playlists 中
        do {
            offset += limit;
            const result = await this.api.getUserPlaylists(undefined, { offset: offset, limit: 50 });
            total = result.body.total;

            const subset = result.body.items.map((playlist) => {
                return { id: playlist.id, name: playlist.name };
            });
            playlists.push(...subset);

        } while ((offset + limit) < total);

        // 搜索名為 'Anti FoMO' 的播放列表（根據我們在 .env 中設定的名稱）
        // 如果未找到，則創建一個新的播放列表
        const index = playlists.findIndex((playlist) => playlist.name === process.env.SPOTIFY_PLAYLIST_NAME);
        if (index >= 0) {
            this.playlist = playlists[index].id;
        }
        else {
            let result;
            await this.api.createPlaylist(process.env.SPOTIFY_USER_ID, process.env.SPOTIFY_PLAYLIST_NAME, { public: false })
                .then(function (data) {
                    result = data.body.id;
                    console.log('已創建 Anti FoMO 播放列表！' + result);
                }, function (err) {
                    console.log('出錯了！', err);
                });
            this.playlist = result;
        }

        console.log("Spotify 準備好了！");
    }

    async refreshAuthToken() {
        const result = await this.api.refreshAccessToken();

        const expiresAt = new Date();
        expiresAt.setSeconds(expiresAt.getSeconds() + result.body.expires_in);
        this.settings.auth.access_token = result.body.access_token;
        this.settings.auth.expires_at = expiresAt;

        this.api.setAccessToken(result.body.access_token);
    }

    async receivedAuthCode(authCode) {
        // 在回調 URL 被調用時接收到授權碼
        // 然後使用此代碼獲取訪問令牌和刷新令牌
        const authFlow = await this.api.authorizationCodeGrant(authCode);
        this.auth = authFlow.body;

        // 保存過期時間，用於刷新令牌
        const expiresAt = new Date();
        expiresAt.setSeconds(expiresAt.getSeconds() + authFlow.body.expires_in);
        this.auth.expires_at = expiresAt;

        // 將兩個令牌傳遞給 Spotify 的庫
        this.api.setAccessToken(this.auth.access_token);
        this.api.setRefreshToken(this.auth.refresh_token);

        // 開始初始化與 Spotify 的連接
        this.initialized();
    }

    async searchTracks(terms, skip = 0, limit = 10) {
        if (!this.isAuthTokenValid()) {
            await this.refreshAuthToken();
        }

        const result = await this.api.searchTracks(terms, { offset: skip, limit: limit });
        return result.body.tracks;
    }

    async queueTrack(track) {
        if (!this.isAuthTokenValid()) {
            await this.refreshAuthToken();
        }
        return this.api.addTracksToPlaylist(this.playlist, [`spotify:track:${track}`]);
    }
}

module.exports = new Spotify();
