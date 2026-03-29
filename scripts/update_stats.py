import os
import re
import json
import urllib.request
from datetime import datetime, timedelta

# Configuration
USERNAME = "bharathkumar000"
SVG_PATH = "streak-stats.svg"
TOKEN = os.getenv("GITHUB_TOKEN")

GRAPHQL_QUERY = """
query($username: String!) {
  user(login: $username) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

def fetch_contribution_data(username, token):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps({"query": GRAPHQL_QUERY, "variables": {"username": username}}).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def calculate_streaks(data):
    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    
    days.sort(key=lambda x: x[0])  # Ensure dates are sorted
    
    total_contributions = calendar["totalContributions"]
    
    current_streak = 0
    longest_streak = 0
    current_streak_start = None
    current_streak_end = None
    longest_streak_start = None
    longest_streak_end = None
    
    temp_streak = 0
    temp_start = None
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for date, count in days:
        if count > 0:
            if temp_streak == 0:
                temp_start = date
            temp_streak += 1
            
            if temp_streak > longest_streak:
                longest_streak = temp_streak
                longest_streak_start = temp_start
                longest_streak_end = date
        else:
            # Streak broken
            if temp_streak > 0:
                # Check if this was the current streak
                # (if it ended yesterday or today)
                if date == today or date == yesterday:
                    # Actually if count is 0 on today, the streak might have ended yesterday
                    pass # handled below
            temp_streak = 0
            temp_start = None

    # Recalculate current streak correctly by walking backwards from today/yesterday
    current_streak = 0
    curr_start = None
    curr_end = None
    
    # Simple way: find the last day with contributions
    last_contributed_day_index = -1
    for i in range(len(days)-1, -1, -1):
        if days[i][1] > 0:
            last_contributed_day_index = i
            break
    
    if last_contributed_day_index != -1:
        last_date = days[last_contributed_day_index][0]
        # Streak is "current" if the last contribution was today or yesterday
        if last_date == today or last_date == yesterday:
            curr_end = last_date
            # Walk backwards
            for i in range(last_contributed_day_index, -1, -1):
                if days[i][1] > 0:
                    current_streak += 1
                    curr_start = days[i][0]
                else:
                    break
    
    return {
        "total": total_contributions,
        "current": current_streak,
        "current_range": f"{format_date(curr_start)} - {format_date(curr_end)}" if curr_start else "No active streak",
        "longest": longest_streak,
        "longest_range": f"{format_date(longest_streak_start)} - {format_date(longest_streak_end)}" if longest_streak_start else "N/A"
    }

def format_date(date_str):
    if not date_str: return ""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%b %-d")

def update_svg(stats):
    with open(SVG_PATH, "r") as f:
        content = f.read()

    # Get current year start date (e.g., Jan 1)
    current_year = datetime.now().year
    total_range = f"Jan 1, {current_year} - Present"

    # Update Total Contributions (x=200)
    # Number (y=145)
    content = re.sub(r'(<text[^>]*x="200"[^>]*y="145"[^>]*>)\s*(\d+)\s*(</text>)', rf'\g<1>{stats["total"]}\g<3>', content)
    # Range (y=222)
    content = re.sub(r'(<text[^>]*x="200"[^>]*y="222"[^>]*>)\s*([^<]+)\s*(</text>)', rf'\g<1>{total_range}\g<3>', content)

    # Update Current Streak (x=600)
    # Number (y=155)
    content = re.sub(r'(<text[^>]*x="600"[^>]*y="155"[^>]*>)\s*(\d+)\s*(</text>)', rf'\g<1>{stats["current"]}\g<3>', content)
    # Range (y=265)
    content = re.sub(r'(<text[^>]*x="600"[^>]*y="265"[^>]*>)\s*([^<]+)\s*(</text>)', rf'\g<1>{stats["current_range"]}\g<3>', content)

    # Update Longest Streak (x=1000)
    # Number (y=145)
    content = re.sub(r'(<text[^>]*x="1000"[^>]*y="145"[^>]*>)\s*(\d+)\s*(</text>)', rf'\g<1>{stats["longest"]}\g<3>', content)
    # Range (y=222)
    content = re.sub(r'(<text[^>]*x="1000"[^>]*y="222"[^>]*>)\s*([^<]+)\s*(</text>)', rf'\g<1>{stats["longest_range"]}\g<3>', content)

    with open(SVG_PATH, "w") as f:
        f.write(content)

if __name__ == "__main__":
    if not TOKEN:
        print("GITHUB_TOKEN not found.")
        exit(1)
    
    data = fetch_contribution_data(USERNAME, TOKEN)
    stats = calculate_streaks(data)
    print(f"Stats calculated: {stats}")
    update_svg(stats)
    print("SVG updated successfully.")
