# Getting Started

Follow these steps to start the project after cloning from GitHub:

### 1. Set Up Environment Variables

- For each `.env.example` file in the project, create a copy named `.env` in the same directory.
- Open each `.env` file and fill in the required API keys and configuration values.

### 2. Install Dependencies with UV

- Make sure you have the [uv package manager](https://github.com/astral-sh/uv) installed.
  - If not, install it by following the instructions in the uv documentation.
- In your project directory, run:
  ```
  uv sync
  ```

### 3. Start the Application

- Run the following command to start the Streamlit app:
  ```
  uv run streamlit run main.py
  ```

You have started your program—enjoy!
