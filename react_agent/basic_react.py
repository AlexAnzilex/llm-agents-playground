import openai
import re 
import httpx
import os 
import csv
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

_ = load_dotenv(find_dotenv())

from openai import OpenAI

client = OpenAI()

class Agent:
    
    def __init__(self, system=""):
        self.system = system
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": system})
            
    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result
    
    def execute(self):
        completion = client.chat.completions.create(
                        model = "gpt-4o-mini",
                        temperature = 0,
                        messages = self.messages)
        
        return completion.choices[0].message.content
    
    
EXPENSES = []

def calculate(expr: str):
    return str(eval(expr))


def load_csv(path: str):
    
    global EXPENSES
    path = path.strip()
    if not os.path.exists(path):
        return f"Path {path} doesn't exist"
    
    data = []
    with open(path, "r", newline ="", encoding = "utf-8") as f:
        reader = csv.DictReader(f)
        required = {"date","category","amount","description"}
        if not required.issubset(set(reader.fieldnames or [])):
            return f"ERROR: CSV must have columns: {sorted(required)}"
        
        for row in reader:
            try:
                amount = float(row["amount"])
            except:
                return f"ERROR: invalid amount '{row.get('amount')}'"
            
            data.append({
                
                "data": row["date"],
                "category": row["category"].strip(),
                "amount": row["amount"],
                "description": row["description"].strip()
            })
            
    
    EXPENSES = data
    return f"Loaded {len(EXPENSES)} expenses from {path}"



def sum_category(category: str):
    
    if not EXPENSES:
        return "ERROR: no expenses loaded. Use load_csv_expenses first."
    
    cat = category.strip()
    if cat.upper() == "ALL":
        total = sum(float(x["amount"]) for x in EXPENSES)
        return f"Total amount: {total:.2f}"
            
    total = sum(float(x["amount"]) for x in EXPENSES if x["category"].lower() == cat.lower())
    return f"TOTAL_{cat}={total:.2f}"


def suggest_cuts(target_saving: str):
    if not EXPENSES:
        return "ERROR: no expenses loaded. Use load_csv_expenses first."

    try:
        target = float(target_saving)
    except:
        return "ERROR: target_saving must be a number like '50'"
    
    by_cat = {}
    for x in EXPENSES:
        by_cat[x["category"]] = by_cat.get(x["category"], 0.0) + float(x["amount"])

  
    ranked = sorted(by_cat.items(), key = lambda kv: kv[1], reverse = True)
    
    suggestions = []
    remaining = target
    
    for cat, total in ranked:
        
        if remaining<= 0:
            break
        
        proposed = min(total*0.10, remaining) 
        proposed = min(proposed, total * 0.30)
        
        if proposed > 0:
            suggestions.append(f"- Cut ~{proposed:.2f} from {cat} (current {total:.2f})")
            remaining -= proposed
    
    if not suggestions:
        return "No suggestions available."

    if remaining > 0:
        suggestions.append(f"(Note: still missing ~{remaining:.2f} to reach the target)")

    return "\n".join(suggestions)
  
def top_category(_unused=None):
    if not EXPENSES:
        return "ERROR: no expenses loaded."
    by_cat = {}
    for x in EXPENSES:
        by_cat[x["category"]] = by_cat.get(x["category"], 0.0) + float(x["amount"])
    cat, total = max(by_cat.items(), key=lambda kv: kv[1])
    return f"TOP_CATEGORY={cat} ({total:.2f})"




known_actions = {
    "calculate": calculate,
    "load_csv_expenses": load_csv,
    "sum_by_category": sum_category,
    "suggest_cuts": suggest_cuts,
    "top_category": top_category,
}


prompt = """
You are a personal finance assistant using ReAct.

Format:
Thought: ...
Action: <tool>: <input>
PAUSE

Then you will receive:
Observation: ...

When you have enough information, output:
Answer: ...

Available tools:
- load_csv_expenses: <path>
- sum_by_category: <category or ALL>
- suggest_cuts: <target_saving_number>
- calculate: <math expression>
- top_category: <no input>

Rules:
- If no CSV is loaded yet and the user asks about expenses, first call load_csv_expenses.
- Use sum_by_category("ALL") for total.
- Keep the final Answer concise and actionable.
- If the user asks for savings suggestions, call suggest_cuts with the target amount.
- top_category: no input
- Use top_category to get the top category.

""".strip()

action_re = re.compile(r'^Action:\s*(\w+):\s*(.*)$', re.MULTILINE)


def query(question, max_turns = 5): 
    count = 0
    bot = Agent(prompt)
    next_prompt = question
    while count < max_turns:
        count += 1
        result = bot(next_prompt)
        print(result)
        
        actions = [m for m in action_re.finditer(result)]
        if not actions:
            return result
        
        if actions:
            action, action_input = actions[0].groups()
            if action not in known_actions:
                raise Exception("Unknown action: {}: {}".format(action, action_input))
            print(" -- running {} {}".format(action, action_input))
            observation = known_actions[action](action_input)
            print("Observation: ", observation)
            next_prompt = "Observation: {}".format(observation)

if __name__ == "__main__":
    
    p = Path("your_path/expenses.csv")
    #example
    print(query(f"Load my expenses from {p.as_posix()} and tell me total and top category, and suggest cuts to save 50."))
