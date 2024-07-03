const spotify = require("./spotify");
const request = require("request-promise");
const LINE_HEADER = {
    "Content-Type": "application/json",
    Authorization: "Bearer " + process.env.LINE_ACCESS_TOKEN
}

const Commands = {
    ADD_TRACK: "ADD_TRACK",
    SEARCH_MORE: "SEARCH_MORE"
}

class lineApp {
    async receivedPostback(event) {
        const payload = JSON.parse(event.postback.data);
        switch (payload.command) {
            case Commands.ADD_TRACK: {
                // 將用戶在 Flex message 中選擇的歌曲加入播放列表
                return this.queueMusic(payload.track);
            }
            case Commands.SEARCH_MORE: {
                // 再次調用 searchMusic 方法並傳遞 payload 中的參數
                return this.searchMusic(payload.terms, payload.skip, payload.limit);
            }
        }
    }

    async queueMusic(track) {
        await spotify.queueTrack(track);
        const message = {
            type: "flex",
            altText: "Thanks! Your track has been added.",
            contents:
            {
                type: "bubble",
                size: "kilo",
                body: {
                    type: "box",
                    layout: "vertical",
                    contents: [
                        {
                            type: "text",
                            contents: [
                                {
                                    type: "span",
                                    text: "Thanks! ",
                                    color: "#1DB954",
                                    weight: "bold",
                                    size: "md"
                                },
                                {
                                    type: "span",
                                    text: "Your track has been added to the BrownJukebox playlist 🎶",
                                    color: "#191414"
                                }
                            ],
                            wrap: true
                        }
                    ]
                },
                styles: {
                    body: {
                        backgroundColor: "#FFFFFF"
                    }
                }
            }
        };
        return message;
    }

    async searchMusic(terms, skip = 0, limit = 10) {

        // 搜索歌曲，一次拉取10首歌
        const queryBegin = skip;
        const queryEnd = limit;
        const result = await spotify.searchTracks(terms, queryBegin, queryEnd);

        if (result.items.length > 0) {
            // 如果還有更多結果，將在 Flex message 中顯示 'More' 按鈕，以便用戶搜索更多歌曲
            const remainingResults = result.total - limit - skip;
            const showMoreButton = (remainingResults > 0);

            // 按受歡迎程度排序結果
            result.items.sort((a, b) => (b.popularity - a.popularity));

            const message = {
                type: "flex",
                altText: "Your Spotify search result",
                contents: {
                    type: "bubble",
                    size: "giga",
                    header: {
                        type: "box",
                        layout: "horizontal",
                        contents: [
                            {
                                type: "image",
                                url: "https://bcrm-i.line-scdn.net/bcrm/uploads/1557539795/public_asset/file/1039/16041313597470536_logo.png",
                                align: "start",
                                size: "xxs",
                                flex: 0,
                                aspectRatio: "4:3"
                            },
                            {
                                type: "text",
                                text: "Powered by Spotify",
                                color: "#ffffff",
                                size: "xxs",
                                align: "end",
                                gravity: "center",
                                position: "relative",
                                weight: "regular"
                            }
                        ],
                        paddingAll: "10px"
                    },
                    body: {
                        type: "box",
                        layout: "vertical",
                        contents: [],
                        backgroundColor: "#191414",
                        spacing: "md"
                    },
                    styles: {
                        header: {
                            backgroundColor: "#1DB954"
                        }
                    }
                }
            };

            // 如果有更多結果，添加 'More' 按鈕，並在 payload 中附上必要的參數，以便用戶想要搜索更多時使用
            if (showMoreButton) {
                message.contents.footer = this.generateMoreButton({
                    command: Commands.SEARCH_MORE,
                    terms: terms,
                    skip: skip + limit,
                    limit: limit
                });
            }

            // 將搜索結果顯示在 Flex message 中，逐一創建每首歌曲的信息
            message.contents.body.contents = result.items.map((track) => {
                this.sortTrackArtwork(track);
                return {
                    type: "box",
                    layout: "horizontal",
                    contents: [
                        {
                            type: "box",
                            layout: "vertical",
                            contents: [
                                {
                                    type: "image",
                                    aspectRatio: "4:3",
                                    aspectMode: "cover",
                                    url: track.album.images.length > 0 ? track.album.images[0].url : ""
                                }
                            ],
                            flex: 0,
                            cornerRadius: "5px",
                            width: "30%",
                            spacing: "none"
                        },
                        {
                            type: "box",
                            layout: "vertical",
                            contents: [
                                {
                                    type: "text",
                                    size: "md",
                                    color: "#1DB954",
                                    style: "normal",
                                    weight: "bold",
                                    text: track.name,
                                    wrap: true
                                },
                                {
                                    type: "text",
                                    size: "xxs",
                                    wrap: true,
                                    color: "#FFFFFF",
                                    text: this.generateArtistList(track)
                                }
                            ],
                            spacing: "none",
                            width: "40%"
                        },
                        {
                            type: "box",
                            layout: "vertical",
                            contents: [
                                {
                                    type: "button",
                                    action: this.generatePostbackButton("Add", { command: Commands.ADD_TRACK, track: track.id }),
                                    style: "primary",
                                    gravity: "bottom",
                                    color: "#1DB954",
                                    height: "sm"
                                }
                            ],
                            spacing: "none",
                            width: "20%"
                        }
                    ],
                    backgroundColor: "#191414",
                    spacing: "xl",
                    cornerRadius: "5px"
                };
            });
            return message;
        }
    }

    generatePostbackButton(title, payload) {
        return {
            type: "postback",
            label: title,
            data: JSON.stringify(payload)
        };
    }

    generateMoreButton(payload) {
        return {
            type: "box",
            layout: "vertical",
            contents: [
                {
                    type: "button",
                    action: {
                        type: "postback",
                        label: "More",
                        data: JSON.stringify(payload)
                    },
                    style: "secondary"
                }
            ],
            backgroundColor: "#191414"
        };
    }

    generateArtistList(track) {
        // 若歌曲有多位藝術家，將每位藝術家的名字以逗號分隔列出
        let artists = "";
        track.artists.forEach((artist) => {
            artists = artists + ", " + artist.name;
        });
        artists = artists.substring(2);
        return artists;
    }

    sortTrackArtwork(track) {
        // 按照專輯圖片的大小從小到大排序
        track.album.images.sort((a, b) => {
            return b.width - a.width;
        });
    }

    async replyMessage(replyToken, message) {
        try {
            await Promise.resolve(request.post({
                headers: LINE_HEADER,
                uri: `${process.env.LINE_MESSAGING_API}/reply`,
                body: JSON.stringify({
                    replyToken: replyToken,
                    messages: [message]
                })
            }))
        } catch (error) {
            console.error(`傳送到 LINE 失敗 (${error})`);
        }
    }
}

module.exports = new lineApp();
