# Anti-FoMO
# FastAPI LINE Bot with Gemini AI and Firebase Integration
> **競賽議題 & 子議題、專案簡介、使用資源為必填**

## 競賽議題 & 子議題
- 團隊名稱：{ City Horse }
- 成員姓名：{段茂萲}, {賴宣佑}
- 競賽議題：{數位心擁：資訊科技促進心理健康}
    - 子議題：{管理資訊，避免FoMO} 
## 專案簡介
- 用途/功能：

- 目標客群&使用情境：
    - 常常會受到社群軟體而感到焦慮的人們
    - 不了解FoMO是什麼的人
- 操作方式：
    - 環境設置
      1.請去申請open api以及 spotify api還有LINE official account進行串聯
      2. line回覆跑很慢請耐心等待
    - 操作方式
        用Line就好
### 使用資源
- 企業資源：
    - { OpenAI }
    我們所選用的語言模型。
    - { Line }
    介面以及系統提供
- 公開資源：
    - {Spotify API}<br>
      連接spotify帳戶並做出個人化推薦
###不重要的事
-會有兩個api撞webhook導致其中一個難以使用的問題，自己做斟酌 嘻
-我們很努力了












## Features

- **Health Check Endpoint**: Simple endpoint to check if the service is running.
- **LINE Webhook Handler**: Handles incoming messages from LINE and responds accordingly.
- **Gemini AI Integration**: Uses Gemini AI to process and generate responses based on the content of the messages.
- **Firebase Integration**: Stores and retrieves chat history from Firebase.

## Prerequisites

- Python 3.7+
- LINE Messaging API account
- Gemini AI API key
- Firebase project
- .env file with the following environment variables:
  - `API_ENV`
  - `LINE_CHANNEL_SECRET`
  - `LINE_CHANNEL_ACCESS_TOKEN`
  - `LOG`
  - `FIREBASE_URL`
  - `GEMINI_API_KEY`
  - `OPEN_API_KEY`

## Installation

1. Clone the repository:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Create a `.env` file in the root directory and add the required environment variables.

## Usage

1. Run the FastAPI application:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload
    ```

2. The application will start and listen for incoming requests on the specified port.

## Endpoints

- **GET /health**: Health check endpoint to verify if the service is running.
- **POST /webhooks/line**: Webhook endpoint to handle incoming messages from LINE.

## Environment Variables

- `API_ENV`: Set to `production` or `develop`.
- `LINE_CHANNEL_SECRET`: Your LINE channel secret.
- `LINE_CHANNEL_ACCESS_TOKEN`: Your LINE channel access token.
- `LOG`: Logging level (default is `WARNING`).
- `FIREBASE_URL`: Your Firebase database URL.
- `GEMINI_API_KEY`: Your Gemini AI API key.
- `OPEN_API_KEY`: Your Open Data API key.

## Logging

The application uses Python's built-in logging module. The log level can be set using the `LOG` environment variable.

## License

This project is licensed under the MIT License.
