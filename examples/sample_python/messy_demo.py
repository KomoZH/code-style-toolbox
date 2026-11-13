import os
import sys
MAX_RETRY=3
class userManager:
  def __init__(self,dbPath):
    self.dbPath=dbPath
    self.retryCount=0
  def loadUsers(self):
    # 加载全部用户
    userList=[]
    for userId in range(MAX_RETRY):
      userList.append({"id":userId,"name":"user_"+str(userId)})
    return userList
  def findUser(self,userList,userId):
    result=None
    for item in userList:
      if item["id"]==userId:
        result=item
    return result
def mainEntry():
  mgr=userManager("demo.db")
  users=mgr.loadUsers()
  found=mgr.findUser(users,1)
  print(found)
if __name__=="__main__":
  mainEntry()
