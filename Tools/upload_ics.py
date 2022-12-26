# from __future__ import print_function
import time
import os.path
import argparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import icalendar as ical


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']


class VVFParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(description="Upload shifts to google calendar")

        # Positional Arguments
        self.add_argument("input_file", type=str, help="input .ics file")

        # Optional Arguments
        self.add_argument("-s", "--seed", type=int, help="SCIP random seed", default=round(time.time()))


parser = VVFParser()
args = parser.parse_args()

print(f"Random seed: {args.seed}\n")

print("Logging in...")
creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

print(f"Processing file {args.input_file}...")
try:
    service = build('calendar', 'v3', credentials=creds)

    with open(args.input_file, "rb") as in_file:
        cal = ical.Calendar.from_ical(in_file.read())
        for component in cal.walk():
            if component.name == "VEVENT":
                # Wait a second between calls as to not overwhelm the API
                time.sleep(1)

                print(f"Processing event {component.get('uid')}")

                if type(component.get('attendee')) == list:
                    attendees = [{'email': str(e).split(":")[1]} for e in component.get('attendee')]
                else:
                    attendees = [{'email': str(component.get('attendee')).split(":")[1]}]

                event = {
                    'id': component.get('uid')+"seed"+str(args.seed),
                    'summary': component.get('summary'),
                    'location': component.get('location'),
                    'description': component.get('description'),
                    'start': {
                        'dateTime': component.get('dtstart').dt.isoformat(),
                        'timeZone': 'Europe/Rome',
                    },
                    'end': {
                        'dateTime': component.get('dtend').dt.isoformat(),
                        'timeZone': 'Europe/Rome',
                    },
                    'attendees': attendees,
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            # {'method': 'email', 'minutes': 24 * 60},
                            {'method': 'popup', 'minutes': 10},
                        ],
                    },
                }

                event = service.events().insert(calendarId='primary', body=event, sendNotifications=True).execute()
                print('Event created: %s' % (event.get('htmlLink')))

except HttpError as error:
    print('An error occurred: %s' % error)

print("Done.")
