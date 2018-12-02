import socket, time, sys, json, pymongo, datetime, unittest

# SYSC 3010 - Automated Aquarium Monitoring Processing Pi
# Version: December 1st 2018
# Author: John Turner

client = pymongo.MongoClient('mongodb://Sahil:Sahil_742995@ds139844.mlab.com:39844/aqua')
db = client.aqua
posts = db.posts

# The IPs for communication, * Make sure both devices are using the same IP types (IPv4 and Eth/WLAN)
toCommIP = "169.254.0.2"  # The IP of the Communication Pi
thisIP = "169.254.187.140"  # The IP of this device

toCommPort = 5001  # Set ports for communication
fromCommPort = 5000

toCommAddress = (toCommIP, toCommPort)  # Combine IPs and Ports into addresses
fromCommAddress = (thisIP, fromCommPort)

toCommSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Initialize UDP Sockets that accept IPs
fromCommSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

fromCommSocket.bind(fromCommAddress)  # Bind receiving sockets to a specific address

updateCount = 20  # Initialize variable so the system updates immediately after being started
updateDelay = 12  # Initialize variable that determines when to update sensor data
appPollTime = 2  # The amount of delay to poll for app requests, also used to delay the sensor data update
feedCounter = 0  # Variable that determines if the feed signal should be sent
feedDelay = 2
Running = True  # Variable to set if the system runs or not


# Processes data from a  JSON packet, converts data to be usable and returns a dictionary
def processData(packet):
    data = json.loads(packet)  # Loads JSON packet into dictionary
    tempRead = data['temp']  # Get the data out of the dictionary
    level = data['level']
    over = data['overflow']
    instruction = data["data"]

    tempRead = tempRead / 1024 * 5000  # Conversion from raw data to usable values
    temp = (tempRead / 10)  # Unit is Celsius

    over = (over * 4 / 600)  # Unit is cm
    level = (level * 4 / 600)  # Unit is cm

    if(level <= 2):  # Check the values to see if there out of a safe range
        instruction = 2  # If the values are bad set the instruction so the app can display an alert
        if(over >= 1):
            instruction = 3
    elif(over >= 1):
        instruction = 4

    temp = round(temp, 2)  # To keep the database clean the values are shortened to only have 2 decimal places
    level = round(level, 2)
    over = round(over, 2)

    update(temp, level, over)  # The processed values are tested and then inserted into the DataBase
    return {"data": instruction, "temp": temp, "level": level, "overflow": over}


# Queries the database for data from a given date, returns the data in a JSON packet
def getPastData(date):
    queryDB = posts.find_one({"Date": date})  # Packet retrieved from the database at the requested date
    return {"data": 9, "temp": queryDB["Temperature"], "level": queryDB["waterLevel"]}#, "overflow": queryDB["overflow"]}


# Sends a request to the Communication Pi to update the sensor data
def getCurrentState():
    toSend = {"data": 5}
    toCommSocket.sendto(json.dumps(toSend).encode(), toCommAddress)  # Sends update instruction to the Comm Pi


def update(temp,level,over):
    currDate = time.gmtime()  # Get the current date
    refinedDate = str(currDate[0]) + "," + str(currDate[1]) + "," + str(currDate[2])  # Split date into year, month, day

    postTest_data = {   # A Packet is created that will be inserted into the DataBase
        'Date': refinedDate,
        'Temperature': temp,
        'waterLevel': level,
        'overflowLevel': over
    }
    if(test(temp, level, over)):  # The data is tested to make sure no bad values go into the DataBase
        store(postTest_data)


def test(temperature, waterLvl, ovrflowLvl):
    assert(waterLvl >= 0),"waterLevel cant be negative"
    assert(temperature >= 0),"temperature cant be negative"
    assert(ovrflowLvl >= 0),"temperature cant be negative"

    assert(waterLvl <= 7), "hardware error, sensor range 0-4 cm"
    assert(temperature <= 40),"hardware error,sensor range 0-40celcius"
    assert(ovrflowLvl <= 7), "hardware error, sensor range 0-4 cm"

    assert(waterLvl != " "),"cannot insert null value"
    assert(temperature != " "), "cannot insert null value"
    assert(ovrflowLvl != " "), "cannot insert null value"
    print("Data is checked and is okay to store")
    return True


def store(data):
    posts.insert_one(data)  # The tested values are inserted into the database


if __name__ == "__main__":
    while Running:
        if(updateCount > updateDelay):  # If it's time to update the data
            getCurrentState()  # Sends update instruction to Comm Pi
            fromCommSocket.settimeout(None)  # Stop the socket from timing out while waiting on new data
            received, add = fromCommSocket.recvfrom(2048)  # Receives data from the Comm Pi
            fromComm = json.loads(received.decode())  # Loads the data into a dictionary
            outData = processData(received)  # Processes the new data
            feedCounter += 1
            if(feedCounter > feedDelay):  # If it's time for feeding set the instruction to feed
                outData["data"] = 7
                feedCounter = 0  # Reset the feed delay
            toCommSocket.sendto(json.dumps(outData).encode(), toCommAddress)  # Send the processed data to the Comm Pi
            updateCount = 0  # Reset the delay

        try:
            fromCommSocket.settimeout(appPollTime)  # The socket stays open and acts as a delay
            appData, add2 = fromCommSocket.recvfrom(2048)
            fromCommAppDict = json.loads(appData.decode())
            queryDate = fromCommAppDict["date"]  # The Date is taken from the packet
            refinedQueryDate = str(queryDate[0]) + "," + str(queryDate[1]) + "," + str(queryDate[2])  # Formatting Date
            retrievedData = getPastData(refinedQueryDate)  # Retrieving the past data from the database
            toCommSocket.sendto(json.dumps(retrievedData).encode(), toCommAddress)  # Sending the old data to the app
        except:
            updateCount += 1  # Each time there is no request counts towards the delay


