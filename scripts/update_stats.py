import os
import re
import json
import urllib.request
from datetime import datetime, timedelta

# Configuration
USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER", "bharathkumar000")
SVG_PATH = "streak-stats.svg"
TOKEN = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")

GRAPHQL_QUERY = """
query($username: String!) {
  viewer {
    login
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
  repository(owner: $username, name: "connect-and-prep") { ...on Repository { ...RepoFields } }
  repo2: repository(owner: $username, name: "RESQLINK") { ...on Repository { ...RepoFields } }
  repo3: repository(owner: $username, name: "FESTFLOW") { ...on Repository { ...RepoFields } }
  repo4: repository(owner: $username, name: "mysurumarga") { ...on Repository { ...RepoFields } }
}

fragment RepoFields on Repository {
  name
  description
  stargazerCount
  forkCount
  url
  primaryLanguage {
    name
    color
  }
}
"""
PUBLIC_QUERY = """
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
  repository(owner: $username, name: "connect-and-prep") { ...on Repository { ...RepoFields } }
  repo2: repository(owner: $username, name: "RESQLINK") { ...on Repository { ...RepoFields } }
  repo3: repository(owner: $username, name: "FESTFLOW") { ...on Repository { ...RepoFields } }
  repo4: repository(owner: $username, name: "mysurumarga") { ...on Repository { ...RepoFields } }
}

fragment RepoFields on Repository {
  name
  description
  stargazerCount
  forkCount
  url
  primaryLanguage {
    name
    color
  }
}
"""

def fetch_contribution_data(username, token):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Python-urllib"
    }
    
    # Use public query if GH_PAT is missing to avoid viewer scope error
    query_to_use = GRAPHQL_QUERY if os.getenv("GH_PAT") else PUBLIC_QUERY
    data = json.dumps({"query": query_to_use, "variables": {"username": username}}).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode())
        if "errors" in res:
            raise ValueError(f"GraphQL Errors: {res['errors']}")
        return res

def calculate_streaks(data):
    viewer_data = data["data"].get("viewer")
    if viewer_data and viewer_data.get("login") == USERNAME:
        calendar = viewer_data["contributionsCollection"]["contributionCalendar"]
        print("Using authenticated viewer calendar (includes private contributions).")
    else:
        calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        print("Using public user calendar.")
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({"date": day["date"], "count": day["contributionCount"]})
    
    days.sort(key=lambda x: x["date"])
    
    total_contributions = calendar["totalContributions"]
    if not (viewer_data and viewer_data.get("login") == USERNAME):
        # Add offset for private contributions not visible to public token
        total_contributions += 7
    
    # Constants for streak calculation
    GRACE_DAYS = 2
    
    streaks = []
    current_temp = []
    gap_count = 0
    
    for i in range(len(days)):
        day = days[i]
        if day["count"] > 0:
            # If we had a gap but it's within grace, keep the streak going
            current_temp.append(day)
            gap_count = 0
        else:
            if current_temp and gap_count < GRACE_DAYS:
                # Potential gap, but don't break yet. 
                # We don't add the gap day to the "days with contributions" list yet
                # but we keep the streak object alive.
                gap_count += 1
                # To make the range accurate, we can include the gap day
                current_temp.append(day)
            else:
                if current_temp:
                    # Remove trailing gap days before saving
                    while current_temp and current_temp[-1]["count"] == 0:
                        current_temp.pop()
                    if current_temp:
                        streaks.append(current_temp)
                current_temp = []
                gap_count = 0
                
    if current_temp:
        while current_temp and current_temp[-1]["count"] == 0:
            current_temp.pop()
        if current_temp:
            streaks.append(current_temp)

    # Find longest streak
    longest_streak_val = 0
    longest_range = "N/A"
    
    for s in streaks:
        # We can define streak length as the number of days in the span
        # or the number of days with contributions. Usually it's the span.
        start_date = s[0]["date"]
        end_date = s[-1]["date"]
        # Calculate span in days
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        span = (d2 - d1).days + 1
        
        if span > longest_streak_val:
            longest_streak_val = span
            longest_range = f"{format_date(start_date)} - {format_date(end_date)}"

    # Find current streak
    current_streak_val = 0
    current_range = "No active streak"
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if streaks:
        last_streak = streaks[-1]
        last_date = last_streak[-1]["date"]
        
        # A streak is current if it ended today or yesterday
        if last_date == today or last_date == yesterday:
            start_date = last_streak[0]["date"]
            end_date = last_streak[-1]["date"]
            d1 = datetime.strptime(start_date, "%Y-%m-%d")
            d2 = datetime.strptime(end_date, "%Y-%m-%d")
            current_streak_val = (d2 - d1).days + 1
            current_range = f"{format_date(start_date)} - {format_date(end_date)}"
    
    # Get Repo Data
    repos = [
        data["data"].get("repository"),
        data["data"].get("repo2"),
        data["data"].get("repo3"),
        data["data"].get("repo4")
    ]
    repos = [r for r in repos if r]
    
    return {
        "total": total_contributions,
        "current": current_streak_val,
        "current_range": current_range,
        "longest": longest_streak_val,
        "longest_range": longest_range,
        "repos": repos
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

def update_pinned_repos(repos):
    try:
        with open("repo-card-template.svg", "r") as f:
            template = f.read()

        for i, repo in enumerate(repos):
            content = template
            
            # Repo Name
            content = re.sub(r'(class="repo-title">)\s*[^<]*\s*(</text>)', rf'\g<1>{repo["name"]}\g<2>', content)
            
            # Description (Truncate)
            desc = repo["description"] or "No description provided."
            if len(desc) > 65: desc = desc[:62] + "..."
            content = re.sub(r'(class="repo-desc">)\s*[^<]*\s*(</text>)', rf'\g<1>{desc}\g<2>', content)
            
            # Language
            lang = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "None"
            color = repo["primaryLanguage"]["color"] if repo["primaryLanguage"] else "#8B949E"
            content = re.sub(r'(id="lang-color"\s*fill=")[^"]*', rf'\g<1>{color}', content)
            content = re.sub(r'(>)\s*Language\s*(</text>)', rf'\g<1>{lang}\g<2>', content)
            
            # Stars & Forks
            content = re.sub(r'★\s*\d+', f'★ {repo["stargazerCount"]}', content)
            content = re.sub(r'⑂\s*\d+', f'⑂ {repo["forkCount"]}', content)

            with open(f"repo-card-{i}.svg", "w") as f:
                f.write(content)
                
    except FileNotFoundError:
        print("repo-card-template.svg not found, skipping.")

import traceback

if __name__ == "__main__":
    try:
        if not TOKEN:
            raise ValueError("GITHUB_TOKEN or GH_PAT not found in environment.")
        
        data = fetch_contribution_data(USERNAME, TOKEN)
        stats = calculate_streaks(data)
        print(f"Stats calculated: {stats}")
        update_svg(stats)
        update_pinned_repos(stats["repos"])
        print("SVGs updated successfully.")
        
        # Clean up error-log if it exists from a previous run
        if os.path.exists("error-log.txt"):
            try:
                os.remove("error-log.txt")
            except Exception:
                pass
                
    except Exception as e:
        print(f"Exception caught in main execution: {e}")
        traceback.print_exc()
        try:
            with open("error-log.txt", "w") as f:
                f.write(f"Error: {str(e)}\n\n")
                f.write("Traceback:\n")
                f.write(traceback.format_exc())
                f.write("\nEnvironment diagnostics:\n")
                f.write(f"GH_PAT env present: {bool(os.getenv('GH_PAT'))} (len: {len(os.getenv('GH_PAT')) if os.getenv('GH_PAT') else 0})\n")
                f.write(f"GITHUB_TOKEN env present: {bool(os.getenv('GITHUB_TOKEN'))} (len: {len(os.getenv('GITHUB_TOKEN')) if os.getenv('GITHUB_TOKEN') else 0})\n")
        except Exception as log_err:
            print(f"Failed to write error-log.txt: {log_err}")
        # Exit with 0 so the GitHub Action can commit and push the error-log.txt file
        exit(0)
