import java.util.ArrayList;
import java.util.List;

public class MessyDemo
{
    private static final int MAX_ITEMS = 100;

    private List<String> user_list = new ArrayList<>();

    public void add_user(String user_name)
    {
        user_list.add(user_name);
    }

    public int find_user(String user_name)
    {
        for (int idx = 0; idx < user_list.size(); idx++)
        {
            if (user_list.get(idx).equals(user_name))
            {
                return idx;
            }
        }
        return -1;
    }

    public static void main(String[] args)
    {
        MessyDemo demo = new MessyDemo();
        demo.add_user("alice");
        demo.add_user("bob");
        int found_index = demo.find_user("bob");
        System.out.println("found: " + found_index);
    }
}
