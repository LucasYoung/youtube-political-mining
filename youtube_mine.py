import csv
from selenium import webdriver
import time
import queue
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import statistics

youtube = None

def parse_configs():

    try:
        read_file = open("myconfigs.json", "r")
        return json.load(read_file)

    except FileNotFoundError:
        raise

def login(driver, account):

    driver.get('http://accounts.google.com/login')

    driver.find_element_by_id("identifierId").send_keys(account.username)
    driver.find_element_by_id("identifierNext").click()

    # wait for next page to load
    time.sleep(1)

    # class name of password element
    class_name = "whsOnd.zHQkBf"
    password_element = driver.find_element_by_class_name(class_name)
    password_element.click()
    password_element.send_keys(account.password)

    next_button = driver.find_element_by_id('passwordNext')
    driver.execute_script("arguments[0].click();", next_button)

def like_video(driver):

    buttons = driver.find_elements_by_id("button")
    for button in buttons:
        label = button.get_attribute("aria-label")
        if label:
            if label.find("like this video along with") != -1:
                print("liking video")
                button.click()
                break  

# returns startpoint
def conservative_initialize(driver):

    last_href = ""
    conservative_queries = ["fox+news", "tucker+carlson", "ben+shapiro", "fake+news"]
    for query in conservative_queries:
        # go to the video and like it
        driver.get("https://www.youtube.com/results?search_query=" + query)
        video = driver.find_element_by_id("video-title")
        last_href = video.get_attribute("href")
        video.click()
        time.sleep(1)
        like_video(driver)
    
    return last_href


class VideoDataPoint():

    def get_comments(self):

        global youtube
        try:
            comments = []
            response = youtube.commentThreads().list(
                part = "snippet",
                videoId = self.video_id
            ).execute()

            for item in response["items"]:
                comment = item["snippet"]["topLevelComment"]
                comments.append(comment["snippet"]["textOriginal"])
            
            return comments
        except HttpError:
            return []

    def aggregate_data(self):

        comments = self.get_comments()
        for comment in comments:
            tb = TextBlob(comment).sentiment.polarity
            if (abs(tb) > 0.95):
                comments_of_interest.append(comment)

        polarities = [abs(TextBlob(comment).sentiment.polarity) for comment in comments]

        mean = statistics.mean(polarities)
        stdev = statistics.stdev(polarities)
        return (mean, stdev)

    def __init__(self, video_id, depth):

        self.video_id = video_id
        self.depth = depth


def is_political(video_id):

    return True

def bfs(driver, startId):

    BRANCHING = 5
    MAX_SIZE = 100

    # queue of tuples: (video_id, depth in search)
    q = queue.Queue()
    q.put((startId, 0))
    depth = 0
    data = []

    while(not q.empty() and q.qsize() < MAX_SIZE):
        node = q.get()
        video_id = node[0]
        depth = node[1]

        if (is_political(video_id)):
            # go to video and like it
            driver.get(video_id)
            time.sleep(1)
            like_video(driver)
            # find recommended elements
            # there are two elements named items. the second one is the recommended column
            items = driver.find_elements_by_id("items")[1]
            thumbnails = items.find_elements_by_id("thumbnail")

            # add BRANCHING number of recommended videos to queue 
            # ensure that MAX_SIZE is not exceeded
            for i in range(min(MAX_SIZE - q.qsize(), BRANCHING)):
                href = thumbnails[i].get_attribute("href")
                data.append(VideoDataPoint(href, depth + 1))
                q.put((href, depth + 1))
                print(q.qsize())

    # now reduce the branching factor to 1

    return data


def experiment_account(account):

    driver = webdriver.Firefox()
    driver.implicitly_wait(10)
    
    login(driver, account)
    time.sleep(3)

    if (not account.initialized):
        if (account.ideology == "Right"):
            startId = conservative_initialize(driver)
        else:
            # liberal initialize
            pass

    bfs(driver, startId)


class Account():

    def __init__(self, csv_row):

        print(csv_row)
        self.username = csv_row[0]
        self.password = csv_row[1]
        # TODO enum for ideology
        self.ideology = csv_row[2]
        self.initialized = True if csv_row[3] == "TRUE" else False
        self.last_video = None if csv_row[4] == "None" else csv_row[4]

def main():

    global youtube
    configs = parse_configs()
    youtube = build(configs['youtube_api_service_name'], configs['youtube_api_version'],
        developerKey=configs['youtube_key'])
    

    with open('accounts.csv', newline='') as csvfile:
        accounts = []
        
        accountreader = csv.reader(csvfile, delimiter = ',', quotechar='|')
        # skip column headers
        accountreader.__next__()
        accounts = [Account(row) for row in accountreader]

        # TODO threading
        experiment_account(accounts[0])
        

if __name__ == "__main__":

    main()