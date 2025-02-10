# Callminder Application

## Overview

The Callminder application is a conversational AI system built using FastAPI. It leverages the SentenceTransformer model for generating sentence embeddings and OpenAI's API for generating responses. The application is designed to handle voice calls and process speech input, providing relevant responses based on the conversation history.

## Features

- Voice call handling using Twilio
- Speech recognition and processing
- Contextual responses using AI
- Entity extraction from user input
- Background loading of the SentenceTransformer model

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.8 or higher
- pip (Python package installer)
- A Twilio account (for voice call handling)
- OpenAI API key (for generating responses)

## Installation

1. **Clone the Repository**

   git clone <repository-url>
   cd <repository-directory>

2. **Create a Virtual Environment**

   ```
   python -m venv venv
   ```

3. **Activate the Virtual Environment**

   - On Windows:

     venv\Scripts\activate 
       or  
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force.\venv\Scripts\activate



   - On macOS/Linux:

     source venv/bin/activate

4. **Install Dependencies**

   Install the required packages using pip:

   pip install -r requirements.txt
   

5. **Set Up Environment Variables**

   Create a `.env` file in the root directory of the project and add the following variables:

   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_FROM_NUMBER=your_twilio_phone_number
   OPENAI_API_KEY=your_openai_api_key
   NGROK_URL=your_ngrok_url
   SMALLEST_API_KEY=your_smallest_api_key
   ```

   Replace the placeholders with your actual credentials.

## Running the Application

1. **Start the Application**

   Run the FastAPI application using Uvicorn:

   ```
   uvicorn app.main:app --reload
   ```

   The application will be accessible at `http://127.0.0.1:8000`.

2. **Using Ngrok (Optional)**

   If you want to expose your local server to the internet (for Twilio to reach your application), you can use Ngrok:

   ```
   ngrok http 8000
   ```

   Copy the Ngrok URL and update the `NGROK_URL` in your `.env` file.


