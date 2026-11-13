#include <iostream>
#include <vector>
#include <string>

const int MAX_ITEMS = 100;

class userManager
{
public:
	void addUser(const std::string& userName)
	{
		userList.push_back(userName);
	}

	int findUser(const std::string& userName)
	{
		for (size_t idx = 0; idx < userList.size(); ++idx)
		{
			if (userList[idx] == userName)
			{
				return static_cast<int>(idx);
			}
		}
		return -1;
	}

private:
	std::vector<std::string> userList;
};

int mainEntry()
{
	userManager mgr;
	mgr.addUser("alice");
	mgr.addUser("bob");
	int foundIndex = mgr.findUser("bob");
	std::cout << "found: " << foundIndex << std::endl;
	return 0;
}
