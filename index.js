const dotenv = require("dotenv");
dotenv.config();
const express = require("express");
const lineApp = require("./lineapp");
const spotify = require("./spotify");
const bodyParser = require("body-parser");

const app = express();
app.use(bodyParser.json());

const port = process.env.PORT || 3000;

app.listen(port, () => {
    console.log(`伺服器已啟動，監聽在 ${port} 端口`);
});

app.post("/webhook", async (req, res) => {
    let event = req.body.events[0];
    let message;
    if (event.type === 'message' && event.message.type === 'text') {
        // 從使用者輸入的文字中搜尋歌曲或藝術家名稱
        let searchInput = event.message.text;
        message = await lineApp.searchMusic(searchInput);

    } else if (event.type === 'postback') {
        // 當使用者按下 Add 按鈕（新增歌曲）或 More 按鈕（繼續搜尋更多歌曲）時
        message = await lineApp.receivedPostback(event);
    }

    await lineApp.replyMessage(event.replyToken, message);
    return res.status(200).send(req.method);
});

app.get("/spotify", (req, res) => {
    // 在使用者登入後，處理回調 URL 並開始與 Spotify 連接
    spotify.receivedAuthCode(req.query.code);
    res.status(200).send("登入成功！");
});
