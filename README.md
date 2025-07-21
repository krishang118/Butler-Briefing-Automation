# Morning Briefing Automation Tool

This is an automated Python tool that compiles a personalized morning briefing and delivers it to the email inbox. The briefing includes latest news headlines from BBC and Times of India, current weather for the city (via OpenWeatherMap), and recent unread emails from the Gmail inbox. All content is elegantly summarized using Google Gemini, with a touch of British butler charm.
 
## Features

- Fetches and summarizes top news from multiple sources
- Retrieves current weather conditions
- Scans Gmail inbox for recent unread emails
- Uses Google Gemini LLM for natural language generation
- Sends the compiled briefing over email
- Can be run immediately or scheduled to run daily at 7:00 AM IST
- Robust error handling and logging

## How to Run

1. Make sure that Python 3.8+ is installed.
2. Clone this repository on your local machine.
3. Get the Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey), and the OpenWeatherMap API Key from the [OpenWeatherMap Website](https://home.openweathermap.org/api_keys).
4. To set up and get the 'Gmail App Password'; which is different from the normal 'Gmail Email Id Password', navigate to the Security section in the Google Account settings, and turn on 2-Step Verification if not already turned on (needed for getting the app password). In the 2-Step Verification section, scroll down to 'App passwords' and generate a new app password from there.
5. Open the `config.json` template file present in the root directory, and fill the necessary credentials; those being the API Keys, the gmail email id, gmail app password, recipient email id (on which the briefing would be sent), and city name (and country code too if outside of India). Save the file with the changes made.
6. Open and run the first cell of the `AI Brief.ipynb` Jupyter Notebook file to install the required dependencies. Run the second cell to run the script for briefing generation immediately. 
7. For schedule-running the automation, run the `AI Brief.py` file (it's the same code, just in a .py file):
  ```bash
  python "AI Brief.py" --schedule
  ```
Alternatively, one can also set up and use Cron Job (for Linux/Mac) or Windows Task Scheduler (for Windows) for the same.

## Contributing

Contributions are welcome!

## License

Distributed under the MIT License. 
