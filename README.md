# Bedrock Proxy

This project provides a simple proxy for Amazon Bedrock's `ConverseStream` operation. It allows you to expose a Bedrock model as a local API endpoint, handling authentication and streaming responses. This can be particularly useful for local development, integration with tools that expect a standard chat API format, or for adding a security layer to your Bedrock access.

## Features

-   Proxies Amazon Bedrock's `ConverseStream` operation.
-   Handles AWS authentication using environment variables (AWS Access Key ID, Secret Access Key, Session Token).
-   Exposes a FastAPI endpoint for chat completions.
-   Outputs streaming responses in a format compatible with Codex-like clients.
-   Configurable AWS Region.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Before you begin, ensure you have the following installed:

-   [Docker](https://www.docker.com/products/docker-desktop)
-   An AWS account with access to Amazon Bedrock and the specific model you intend to use (e.g., `qwen.qwen3-coder-30b-a3b-v1:0`). Ensure that Bedrock is enabled in your chosen AWS region.

### Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/asfolcini/bedrock_proxy.git
    cd bedrock_proxy
    ```

2.  **Configure AWS Credentials:**
    Create a `.env` file in the root of the project directory. This file will store your AWS credentials securely and will not be committed to Git. You can use the provided `.env.example` as a template.

    ```dotenv
    # .env
    AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
    AWS_SESSION_TOKEN=YOUR_AWS_SESSION_TOKEN
    ```
    **Note:** `AWS_SESSION_TOKEN` is required if you are using temporary credentials (e.g., from AWS SSO or STS assume-role). If you are using long-lived IAM user credentials, you might omit `AWS_SESSION_TOKEN`.

3.  **Build and Run the Docker Container:**
    ```bash
    docker compose up -d --build
    ```
    This command will build the Docker image and start the proxy service in the background.

## Usage

The proxy exposes an API endpoint on `http://localhost:8000`.

### Chat Completions Endpoint

-   **Endpoint:** `/v1/responses` or `/responses` (POST)
-   **Authentication:** Requires a `Bearer Token` in the `Authorization` header. The token is defined by `REQUIRED_TOKEN` in `main.py` (default: "sfl-token-llm-very-secret").
-   **Request Body:** Expects a JSON payload similar to standard chat completion APIs, including `model` and `messages`.
-   **Response:** Streams Server-Sent Events (SSE) with the model's response.

#### Example Request using `curl`

First, ensure you have the `REQUIRED_TOKEN` from `main.py`. By default, it's `sfl-token-llm-very-secret`.

```bash
curl -X POST http://localhost:8000/v1/responses 
  -H "Content-Type: application/json" 
  -H "Authorization: Bearer sfl-token-llm-very-secret" 
  -d '{
    "model": "qwen.qwen3-coder-30b-a3b-v1:0",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

#### Example Response (Streaming SSE)

```
data: {"type": "response.created", "response": {"id": "resp_12345", "status": "in_progress"}}

data: {"type": "response.output_item.added", "output_index": 0, "item": {"type": "message", "role": "assistant", "content": []}}

data: {"type": "response.content_part.added", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": "The"}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": " capital"}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": " of"}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": " France"}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": " is"}

data: {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": " Paris."}

data: {"type": "response.output_text.done", "output_index": 0, "content_index": 0, "text": "The capital of France is Paris."}

data: {"type": "response.content_part.done", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "The capital of France is Paris."}}

data: {"type": "response.output_item.done", "output_index": 0, "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "The capital of France is Paris."}]}}

data: {"type": "response.completed", "response": {"id": "resp_12345", "status": "completed"}}

data: [DONE]
```

## Configuration

-   **`AWS_REGION`**: The AWS region where your Bedrock model is available. This can be set in your `.env` file or directly as an environment variable (default: `eu-south-1`).
-   **`REQUIRED_TOKEN`**: The bearer token required for authentication to the proxy's endpoints. This is hardcoded in `main.py` and can be changed if needed.

## Development

### Running Locally (without Docker)

If you prefer to run the FastAPI application directly, you can do so after installing dependencies:

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set environment variables:**
    Ensure your AWS credentials are set as environment variables in your shell where you run the application:
    ```bash
    export AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
    export AWS_SESSION_TOKEN=YOUR_AWS_SESSION_TOKEN # Optional for long-lived credentials
    export AWS_REGION=eu-south-1
    ```
3.  **Run the application:**
    ```bash
    python main.py
    ```
    Or, using `uvicorn` directly:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

## Contributing

Feel free to open issues or submit pull requests if you have suggestions or improvements.

## License

This project is open-source and available under the [MIT License](LICENSE).
(Note: A `LICENSE` file is not included in this project, but it's good practice to have one.)
