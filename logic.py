import hashlib
from datetime import datetime, timedelta
import streamlit as st
from supabase import create_client, Client

def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def hash_pass(p): 
    return hashlib.sha256(p.encode()).hexdigest()

def register_user(username, password):
    existing = supabase.table("users").select("id").eq("username", username).execute().data
    if existing: return False, "Username taken."
    
    res = supabase.table("users").insert({"username": username, "password": hash_pass(password)}).execute()
    new_user = res.data[0]
    
    # Spawn default isolated categories only
    cats = [
        {"owner_id": new_user["id"], "name": "Food & Dining", "icon": "🍔", "type": "expense"},
        {"owner_id": new_user["id"], "name": "Rent", "icon": "🏠", "type": "expense"},
        {"owner_id": new_user["id"], "name": "Shopping", "icon": "🛍️", "type": "expense"},
        {"owner_id": new_user["id"], "name": "Salary", "icon": "💰", "type": "income"}
    ]
    supabase.table("categories").insert(cats).execute()
    
    return True, new_user

def login_user(username, password):
    res = supabase.table("users").select("*").eq("username", username).eq("password", hash_pass(password)).execute().data
    if res: return True, res[0]
    return False, "Invalid credentials."

def load_data(user_id, username):
    data = {
        "friends": supabase.table("friends").select("*").eq("owner_id", user_id).execute().data,
        "accounts": supabase.table("accounts").select("*").eq("owner_id", user_id).execute().data,
        "categories": supabase.table("categories").select("*").eq("owner_id", user_id).execute().data,
        "transactions": supabase.table("transactions").select("*").eq("owner_id", user_id).execute().data,
        "recurring": supabase.table("recurring").select("*").eq("owner_id", user_id).execute().data,
    }
    
    # Cross tenant Universal Fetch (Safe because of app isolation)
    all_exps = supabase.table("expenses").select("*").execute().data
    my_exps = [e for e in all_exps if e.get("creator_username") == username or e.get("payer_username") == username or username in e.get("participants", {})]
    data["expenses"] = my_exps
    
    all_pays = supabase.table("payments").select("*").execute().data
    my_pays = [p for p in all_pays if p.get("from_username") == username or p.get("to_username") == username]
    data["payments"] = my_pays
    
    return data

def add_friend(owner_id, name, linked_username=None):
    if linked_username:
        u = supabase.table("users").select("id").eq("username", linked_username).execute().data
        if not u: return False, "Target user not found on global server!"
        
    f = {"owner_id": owner_id, "name": name, "linked_username": linked_username, "active": True}
    res = supabase.table("friends").insert(f).execute()
    return True, res.data[0]

def remove_friend(owner_id, friend_id):
    supabase.table("friends").update({"active": False}).eq("id", friend_id).eq("owner_id", owner_id).execute()
    return True

def add_expense(creator_username, description, amount, payer_username, participants_dict):
    # participants_dict comes in as { "bob": {"amount": 250, "status": "pending"} }
    for usr, payload in participants_dict.items():
        if usr == creator_username:
            payload["status"] = "accepted"
        else:
            payload["status"] = "pending"
            
    exp = {
        "creator_username": creator_username,
        "description": description,
        "amount": amount,
        "payer_username": payer_username,
        "participants": participants_dict,
        "date": datetime.now().isoformat()
    }
    res = supabase.table("expenses").insert(exp).execute()
    return True, res.data[0]

def delete_expense(exp_id):
    supabase.table("expenses").delete().eq("id", exp_id).execute()
    # Also delete connected transactions
    supabase.table("transactions").delete().eq("linked_split_id", exp_id).execute()
    return True

def answer_expense(exp_id, username, accept=True):
    exp = supabase.table("expenses").select("*").eq("id", exp_id).execute().data[0]
    parts = exp["participants"]
    if username in parts:
        if accept: parts[username]["status"] = "accepted"
        else: parts[username]["status"] = "rejected"
        supabase.table("expenses").update({"participants": parts}).eq("id", exp_id).execute()
    return True

def calculate_balances(data, username):
    balances = {}
    for f in data.get("friends", []):
        target_key = f.get("linked_username") if f.get("linked_username") else f["name"]
        balances[target_key] = 0.0
            
    for exp in data.get("expenses", []):
        payer = exp["payer_username"]
        parts = exp.get("participants", {})
        
        amt_paid_by_me = float(exp["amount"]) if payer == username else 0.0
        my_share = 0.0
        
        if username in parts and parts[username].get("status") != "rejected":
            my_share = float(parts[username]["amount"])
            
        if payer == username:
            for p_user, payload in parts.items():
                if p_user != username and payload.get("status") != "rejected":
                    if p_user in balances: balances[p_user] += float(payload["amount"])
                    else: balances[p_user] = float(payload["amount"])
        else:
            if username in parts and parts[username].get("status") != "rejected":
                if payer in balances: balances[payer] -= my_share
                else: balances[payer] = -my_share

    for pay in data.get("payments", []):
        if pay["status"] == "accepted":
            if pay["from_username"] == username:
                tgt = pay["to_username"]
                if tgt in balances: balances[tgt] += float(pay["amount"])
                else: balances[tgt] = float(pay["amount"])
            elif pay["to_username"] == username:
                tgt = pay["from_username"]
                if tgt in balances: balances[tgt] -= float(pay["amount"])
                else: balances[tgt] = -float(pay["amount"])

    return balances

def simplify_debts(balances):
    debtors = []
    creditors = []
    for uid, bal in balances.items():
        if bal < -0.01: debtors.append({"id": uid, "amount": -bal})
        elif bal > 0.01: creditors.append({"id": uid, "amount": bal})
            
    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)
    
    settlements = []
    i = 0
    j = 0
    while i < len(debtors) and j < len(creditors):
        debt = debtors[i]
        cred = creditors[j]
        settle_amt = min(debt["amount"], cred["amount"])
        if settle_amt > 0.01:
            settlements.append({
                "from": debt["id"],
                "to": cred["id"],
                "amount": float(round(settle_amt, 2))
            })
        debt["amount"] -= settle_amt
        cred["amount"] -= settle_amt
        if debt["amount"] < 0.01: i += 1
        if cred["amount"] < 0.01: j += 1
    return settlements

def add_transaction(owner_id, t_type, amount, category_id, description, account_id, date=None, linked_split_id=None):
    tx = {
        "owner_id": owner_id,
        "type": t_type,
        "amount": amount,
        "category_id": category_id,
        "account_id": account_id,
        "description": description,
        "date": date if date else datetime.now().isoformat(),
        "linked_split_id": linked_split_id
    }
    res = supabase.table("transactions").insert(tx).execute()
    return True, res.data[0]

def delete_transaction(tx_id):
    supabase.table("transactions").delete().eq("id", tx_id).execute()
    return True

def request_settlement(from_username, to_username, amount):
    pay = {
        "from_username": from_username,
        "to_username": to_username,
        "amount": amount,
        "status": "pending",
        "date": datetime.now().isoformat()
    }
    supabase.table("payments").insert(pay).execute()
    return True

def accept_settlement(pay_id, owner_id):
    pay_data = supabase.table("payments").select("*").eq("id", pay_id).execute().data
    if not pay_data: return False
    pay = pay_data[0]
    
    if pay["status"] == "pending":
        supabase.table("payments").update({"status": "accepted"}).eq("id", pay_id).execute()
        return True
    return False

def add_account(owner_id, name, initial_balance=0.0, icon="🏦"):
    acc = {"owner_id": owner_id, "name": name, "initial_balance": float(initial_balance), "icon": icon}
    res = supabase.table("accounts").insert(acc).execute()
    return True, res.data[0]

def add_category(owner_id, name, icon, t_type):
    cat = {"owner_id": owner_id, "name": name, "icon": icon, "type": t_type}
    res = supabase.table("categories").insert(cat).execute()
    return True, res.data[0]

def add_recurrence(owner_id, t_type, amount, category_id, account_id, description, frequency, next_date=None):
    rec = {
        "owner_id": owner_id,
        "type": t_type,
        "amount": amount,
        "category_id": category_id,
        "account_id": account_id,
        "description": description,
        "frequency": frequency,
        "next_date": next_date if next_date else datetime.now().isoformat(),
        "active": True
    }
    res = supabase.table("recurring").insert(rec).execute()
    return True, res.data[0]

def stop_recurrence(owner_id, rec_id):
    supabase.table("recurring").update({"active": False}).eq("id", rec_id).eq("owner_id", owner_id).execute()
    return True

def process_recurrences():
    recs = supabase.table("recurring").select("*").eq("active", True).execute().data
    now_dt = datetime.now()
    tx_batch = []
    
    for rec in recs:
        next_dt = datetime.fromisoformat(rec["next_date"])
        loops = 0
        updated = False
        
        while next_dt <= now_dt and loops < 500:
            tx = {
                "owner_id": rec["owner_id"],
                "type": rec["type"],
                "amount": rec["amount"],
                "category_id": rec["category_id"],
                "account_id": rec.get("account_id"),
                "description": f"🔄 {rec['description']}",
                "date": next_dt.isoformat(),
                "linked_split_id": None
            }
            tx_batch.append(tx)
            
            if rec["frequency"] == "Daily": next_dt += timedelta(days=1)
            elif rec["frequency"] == "Weekly": next_dt += timedelta(weeks=1)
            elif rec["frequency"] == "Monthly":
                month = next_dt.month
                year = next_dt.year
                if month == 12: month = 1; year += 1
                else: month += 1
                try: next_dt = next_dt.replace(year=year, month=month)
                except ValueError: next_dt = next_dt.replace(year=year, month=month, day=28)
                    
            rec["next_date"] = next_dt.isoformat()
            updated = True
            loops += 1
            
        if updated:
            supabase.table("recurring").update({"next_date": rec["next_date"]}).eq("id", rec["id"]).execute()
            
    if tx_batch:
        supabase.table("transactions").insert(tx_batch).execute()
