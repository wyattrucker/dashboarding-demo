import requests
import gspread
from google.oauth2.service_account import Credentials
import time

# --- CONFIG ---
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Steam Dashboard Data"

# --- GOOGLE SHEETS AUTH ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# --- HEADERS ---
headers = [
    "App ID", "Name", "Release Date", "Original Price (USD)", 
    "Current Price (USD)", "Discount %", "Review Score", 
    "Review Count", "Review Summary", "Peak Concurrent Players",
    "Genre", "Developer"
]
sheet.clear()
sheet.append_row(headers)

# --- FETCH 2026 GAMES ---
def get_2026_game_ids():
    url = "https://store.steampowered.com/search/results/"
    params = {
        "sort_by": "Reviews_DESC",
        "json": 1,
        "filter": "released",
        "os": "win",
        "release_time_from": 1735689600,  # Jan 1 2026
        "release_time_to": 1767225600,    # Dec 31 2026
        "count": 50
    }
    headers_req = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    response = requests.get(url, params=params, headers=headers_req)
    data = response.json()

    print(f"Total results reported: {data.get('total_count', 0)}")
    print(f"Items returned: {len(data.get('items', []))}")

    app_ids = []
    for item in data.get("items", []):
        try:
            logo = item.get("logo", "")
            parts = logo.split("/apps/")
            if len(parts) > 1:
                aid = int(parts[1].split("/")[0])
                app_ids.append(aid)
        except:
            continue

    print(f"App IDs extracted: {len(app_ids)}")
    return app_ids

# --- FETCH GAME DETAILS ---
def get_game_details(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=us&l=en"
    response = requests.get(url)
    data = response.json()

    if not data.get(str(app_id), {}).get("success"):
        return None

    game = data[str(app_id)]["data"]

    # Only include 2026 releases
    release_date = game.get("release_date", {}).get("date", "")
    if "2026" not in release_date:
        return None

    # Price
    if game.get("is_free"):
        original_price = 0
        current_price = 0
        discount = 0
    elif game.get("price_overview"):
        p = game["price_overview"]
        original_price = p["initial"] / 100
        current_price = p["final"] / 100
        discount = p["discount_percent"]
    else:
        original_price = current_price = discount = "N/A"

    # Reviews
    review_score = game.get("metacritic", {}).get("score", "N/A")
    
    # Review summary from recommendations
    rec = game.get("recommendations", {})
    review_count = rec.get("total", "N/A")

    # Genres
    genres = ", ".join([g["description"] for g in game.get("genres", [])])

    # Developer
    developer = ", ".join(game.get("developers", ["N/A"]))

    return {
        "app_id": app_id,
        "name": game.get("name", "N/A"),
        "release_date": release_date,
        "original_price": original_price,
        "current_price": current_price,
        "discount": discount,
        "review_score": review_score,
        "review_count": review_count,
        "review_summary": "N/A",
        "peak_players": "N/A",  # fetched separately
        "genre": genres,
        "developer": developer
    }

# --- FETCH PEAK PLAYERS ---
def get_peak_players(app_id):
    url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
    try:
        url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={app_id}"
        response = requests.get(url)
        data = response.json()
        return data.get("response", {}).get("player_count", "N/A")
    except:
        return "N/A"

# --- MAIN ---
print("Fetching 2026 Steam games...")
app_ids = get_2026_game_ids()

print(f"\nFetching details for {len(app_ids)} games...")
games = []
for app_id in app_ids:
    details = get_game_details(app_id)
    if details:
        # Fetch current player count
        details["peak_players"] = get_peak_players(app_id)
        games.append(details)
        print(f"  Added: {details['name']} | Reviews: {details['review_count']} | Players: {details['peak_players']}")
    else:
        print(f"  Skipped: {app_id}")
    time.sleep(1.5)

# Sort by review count, take top 10
def safe_int(val):
    try:
        return int(val)
    except:
        return 0

games.sort(key=lambda x: safe_int(x["review_count"]), reverse=True)
top_10 = games[:10]

print(f"\nWriting top {len(top_10)} games to Google Sheets...")
for game in top_10:
    sheet.append_row([
        game["app_id"], game["name"], game["release_date"],
        game["original_price"], game["current_price"], game["discount"],
        game["review_score"], game["review_count"], game["review_summary"],
        game["peak_players"], game["genre"], game["developer"]
    ])
    print(f"  Written: {game['name']}")

print("\nDone! Check your Google Sheet.")