# 1. Start from a lightweight Python base image
FROM python:3.10-slim

# 2. Set a working directory inside the container
WORKDIR /app

# 3. Copy requirements first (for caching)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your bot code
COPY . .

# 6. Run your bot
CMD ["python", "forex_bot.py"]
