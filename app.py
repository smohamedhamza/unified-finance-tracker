import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from logic import (load_data, register_user, login_user, add_friend, remove_friend, add_expense, answer_expense,
                   calculate_balances, simplify_debts, delete_expense, add_transaction, delete_transaction,
                   request_settlement, accept_settlement, add_category, add_account, add_recurrence, stop_recurrence, process_recurrences)

st.set_page_config(page_title="FinTracker & Splitwise", page_icon="💸", layout="wide")

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "user" not in st.session_state:
    st.title("💸 Unified Finance Tracker")
    st.markdown("Welcome to the isolated Multi-Tenant cloud. Please log in.")
    t_login, t_signup = st.tabs(["Login", "Create Account"])
    
    with t_login:
        with st.form("login"):
            l_usr = st.text_input("Username")
            l_pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                if l_usr and l_pwd:
                    succ, res = login_user(l_usr, l_pwd)
                    if succ:
                        st.session_state["user"] = res
                        st.rerun()
                    else: st.error(res)
                    
    with t_signup:
        with st.form("signup"):
            s_usr = st.text_input("Username (Global ID)")
            s_pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Register"):
                if s_usr.strip() and s_pwd.strip():
                    succ, res = register_user(s_usr.strip(), s_pwd.strip())
                    if succ:
                        st.session_state["user"] = res
                        st.rerun()
                    else: st.error(res)
    st.stop()

# ==========================================
# MAIN APP INIT
# ==========================================
me = st.session_state["user"]
me_id = me["id"]
me_username = me["username"]

col_t1, col_t2 = st.columns([5, 1])
col_t1.title(f"💸 {me_username}'s Finance Tracker")
if col_t2.button("Logout", use_container_width=True):
    del st.session_state["user"]
    st.rerun()
    
# Process background schedulers
process_recurrences()
data = load_data(me_id, me_username)

accounts = data.get("accounts", [])
acc_map = {a["id"]: a for a in accounts}
cats = data.get("categories", [])

# Dynamic Friend Mapping
all_friends = data.get("friends", [])
active_friends = [f for f in all_friends if f.get("active", True)]

target_mapping = {f"Me (@{me_username})": me_username}
for f in active_friends:
    if f.get("linked_username"): disp = f"{f['name']} (@{f['linked_username']})"
    else: disp = f"{f['name']} (Local)"
    target_mapping[disp] = f.get("linked_username") or f["name"]

target_names = list(target_mapping.keys())

st.markdown("---")
tab_personal, tab_splitwise, tab_friends = st.tabs(["💰 Personal Finance", "🤝 Splitwise Groups", "👥 Friends & Network"])

# ==========================================
# TAB: PERSONAL FINANCE
# ==========================================
with tab_personal:
    tot_bal = sum([float(a["initial_balance"]) for a in accounts])
    for tx in data.get("transactions", []):
        if tx["type"] == "income": tot_bal += float(tx["amount"])
        else: tot_bal -= float(tx["amount"])
        
    st.markdown(f"### Total Net Worth: **₹{tot_bal:.2f}**")
    
    act_cols = st.columns(len(accounts) if accounts else 1)
    for i, a in enumerate(accounts):
        a_bal = float(a["initial_balance"])
        for tx in data.get("transactions", []):
            if tx.get("account_id") == a["id"]:
                if tx["type"] == "income": a_bal += float(tx["amount"])
                else: a_bal -= float(tx["amount"])
        act_cols[i % len(act_cols)].metric(f"{a['icon']} {a['name']}", f"₹{a_bal:.2f}")

    in_col, out_col, list_col = st.columns([1, 1, 2])

    with in_col:
        st.subheader("Add Income")
        with st.container(border=True):
            if not accounts: st.error("Create an account below to log income!")
            in_amt = st.number_input("Amount (₹)", min_value=0.01, key="in_amt")
            in_desc = st.text_input("Description", key="in_desc")
            in_cat = st.selectbox("Category", [c for c in cats if c["type"] == "income"], format_func=lambda x: f"{x['icon']} {x['name']}", key="in_cat")
            in_acc = st.selectbox("Deposit To", accounts, format_func=lambda x: f"{x['icon']} {x['name']}", key="in_acc")
            
            hc1, hc2 = st.columns(2)
            in_d = hc1.date_input("Date", datetime.today(), key="in_d")
            in_t = hc2.time_input("Time", datetime.now().time(), key="in_t", step=60)
            
            in_rec = st.selectbox("Repeat", ["None", "Daily", "Weekly", "Monthly"], key="in_rec")
            
            if st.button("Log Income", use_container_width=True, disabled=not accounts):
                target_dt = datetime.combine(in_d, in_t).isoformat()
                if in_rec == "None":
                    add_transaction(me_id, "income", in_amt, in_cat["id"], in_desc, in_acc["id"], target_dt)
                else:
                    add_recurrence(me_id, "income", in_amt, in_cat["id"], in_acc["id"], in_desc, in_rec, target_dt)
                st.success("Income Logged!")
                st.rerun()

    with out_col:
        st.subheader("Add Expense")
        with st.container(border=True):
            if not accounts: st.error("Create an account below to log expenses!")
            out_amt = st.number_input("Amount (₹)", min_value=0.01, key="out_amt")
            out_desc = st.text_input("Description", key="out_desc")
            out_cat = st.selectbox("Category", [c for c in cats if c["type"] == "expense"], format_func=lambda x: f"{x['icon']} {x['name']}", key="out_cat")
            out_acc = st.selectbox("Withdraw From", accounts, format_func=lambda x: f"{x['icon']} {x['name']}", key="out_acc")

            hc3, hc4 = st.columns(2)
            out_d = hc3.date_input("Date", datetime.today(), key="out_d")
            out_t = hc4.time_input("Time", datetime.now().time(), key="out_t", step=60)
            
            out_rec = st.selectbox("Repeat", ["None", "Daily", "Weekly", "Monthly"], key="out_rec")

            if st.button("Log Expense", use_container_width=True, disabled=not accounts):
                target_dt = datetime.combine(out_d, out_t).isoformat()
                if out_rec == "None":
                    add_transaction(me_id, "expense", out_amt, out_cat["id"], out_desc, out_acc["id"], target_dt)
                else:
                    add_recurrence(me_id, "expense", out_amt, out_cat["id"], out_acc["id"], out_desc, out_rec, target_dt)
                st.success("Expense Logged!")
                st.rerun()

    with list_col:
        st.subheader("Transaction History")
        if not data.get("transactions"):
            st.info("No personal transactions yet.")
        else:
            sorted_txs = sorted(data["transactions"], key=lambda k: k.get("date", ""), reverse=True)
            for tx in sorted_txs:
                cat = next((c for c in cats if c["id"] == tx["category_id"]), {"icon":"❔", "name":"Unknown"})
                acc_tmp = acc_map.get(tx.get("account_id"))
                acc_nm = f"{acc_tmp.get('icon', '🏦')} {acc_tmp['name']}" if acc_tmp else "Unknown"
                
                dt_obj = datetime.fromisoformat(tx.get("date", datetime.now().isoformat()))
                st.markdown(f"**{cat['icon']} {cat['name']}**  •  {dt_obj.strftime('%b %d, %H:%M')}")
                st.caption(f"{tx['description']} | Account: {acc_nm}")
                
                cola, colb = st.columns([3, 1])
                cola.write(f"₹{float(tx['amount']):.2f} ({tx['type']})")
                if colb.button("❌", key=f"del_tx_{tx['id']}"):
                    delete_transaction(tx["id"])
                    st.rerun()
                st.divider()

    st.markdown("---")
    st.subheader("⚙️ Vault Management")
    c_m1, c_m2, c_m3 = st.columns(3)
    
    with c_m1:
        with st.expander("🏦 Add Account"):
            a_nm = st.text_input("Account Name")
            a_icon = st.selectbox("Icon", ["🏦", "💵", "💳", "📱", "🪙", "🐷"])
            a_bal = st.number_input("Starting Balance (₹)", min_value=0.0)
            if st.button("Create Account"):
                if a_nm.strip():
                    add_account(me_id, a_nm.strip(), a_bal, a_icon)
                    st.success("Account added!")
                    st.rerun()

    with c_m2:
        with st.expander("🏷️ Add Category"):
            c_nm = st.text_input("Category Name")
            c_icon = st.selectbox("Category Icon", ["🍔", "🏠", "🛍️", "💰", "⛽", "🏥", "🎓", "✈️", "🚗", "💻", "🎮", "💡"])
            c_type = st.selectbox("Type", ["expense", "income"])
            if st.button("Create Category"):
                if c_nm.strip():
                    add_category(me_id, c_nm.strip(), c_icon, c_type)
                    st.success("Category added!")
                    st.rerun()

    with c_m3:
        with st.expander("🔄 Active Subscriptions"):
            recs = data.get("recurring", [])
            active_recs = [r for r in recs if r.get("active", True)]
            if not active_recs:
                st.info("No active recurring schedules.")
            else:
                for r in active_recs:
                    rc1, rc2 = st.columns([3, 1])
                    rc1.write(f"**{r['description']}** (₹{r['amount']})")
                    rc1.caption(f"Repeats {r['frequency']} • Next: {r['next_date'].split('T')[0]}")
                    if rc2.button("Stop", key=f"stop_{r['id']}"):
                        stop_recurrence(me_id, r['id'])
                        st.rerun()

# ==========================================
# TAB: SPLITWISE GROUPS
# ==========================================
with tab_splitwise:
    col_bal, col_act = st.columns([1, 2])
    
    balances = calculate_balances(data, me_username)
    
    with col_bal:
        st.subheader("📬 Pending Inbox")
        # Pending Expenses
        pending_exp = [e for e in data.get("expenses", []) if me_username in e.get("participants", {}) and e["participants"][me_username].get("status") == "pending"]
        if pending_exp:
            for e in pending_exp:
                with st.container(border=True):
                    st.write(f"**@{e['creator_username']}** added **{e['description']}** (₹{e['amount']})")
                    my_share = e['participants'][me_username]['amount']
                    st.write(f"Your owes: ₹{my_share}")
                    c1, c2 = st.columns(2)
                    if c1.button("Accept", key=f"acc_exp_{e['id']}"):
                        answer_expense(e["id"], me_username, True)
                        # Add literal expense to personal ledger
                        def_acc = accounts[0]["id"] if accounts else None
                        add_transaction(me_id, "expense", my_share, "cat_split", f"[Group] {e['description']}", def_acc, e["date"], e["id"])
                        st.rerun()
                    if c2.button("Reject", key=f"rej_exp_{e['id']}"):
                        answer_expense(e["id"], me_username, False)
                        st.rerun()
                        
        # Pending Payments
        pending_pay = [p for p in data.get("payments", []) if p["to_username"] == me_username and p["status"] == "pending"]
        if pending_pay:
            for p in pending_pay:
                with st.container(border=True):
                    st.write(f"**@{p['from_username']}** sent settlement: ₹{p['amount']}")
                    if st.button("Confirm Transfer", key=f"conf_pay_{p['id']}"):
                        accept_settlement(p["id"], me_id)
                        st.rerun()
        
        if not pending_exp and not pending_pay:
            st.info("Inbox clear! No pending actions.")
            
        st.markdown("---")
        st.subheader("⚖️ Who Owes Who?")
        net_bal = 0.0
        for uid, bal in balances.items():
            if bal > 0.01:
                st.success(f"{uid} owes you ₹{bal:.2f}")
                net_bal += bal
            elif bal < -0.01:
                st.error(f"You owe {uid} ₹{-bal:.2f}")
                net_bal += bal
        if net_bal == 0.0:
            st.info("You're all settled up!")
        else:
            st.markdown(f"**Net Position:** {('₹'+str(round(net_bal,2))) if net_bal>=0 else ('-₹'+str(round(-net_bal,2)))}")
            
        debts = simplify_debts(balances)
        if debts:
            with st.expander("Show Optimal Settlements"):
                for d in debts: st.write(f"{d['from']} ➡️ {d['to']}: ₹{d['amount']:.2f}")

    with col_act:
        st.subheader("🍕 Add Group Expense")
        with st.container(border=True):
            if not accounts: st.error("You must create an account first to log an expense!")
            exp_desc = st.text_input("Description", placeholder="Pizza logic")
            exp_amt = st.number_input("Total Amount (₹)", min_value=0.01)
            
            c_p1, c_p2 = st.columns(2)
            exp_payer = c_p1.selectbox("Who Paid?", target_names)
            exp_acc = c_p2.selectbox("Account (If you paid)", accounts, format_func=lambda x: f"{x['icon']} {x['name']}")
            
            exp_parts = st.multiselect("Who Split It?", target_names, default=[target_names[0]])
            
            if st.button("Add Expense", use_container_width=True, disabled=not accounts):
                if not exp_parts: st.error("Select participants!")
                else:
                    split_val = float(exp_amt) / len(exp_parts)
                    p_dict = {}
                    for p in exp_parts:
                        p_dict[target_mapping[p]] = {"amount": split_val}
                    
                    add_expense(me_username, exp_desc, float(exp_amt), target_mapping[exp_payer], p_dict)
                    
                    # Log personal transaction if creator was the payer
                    if target_mapping[exp_payer] == me_username:
                        add_transaction(me_id, "expense", float(exp_amt), "cat_split", f"[Paid Group] {exp_desc}", exp_acc["id"], datetime.now().isoformat())
                    
                    st.success("Expense added! (Notified friends)")
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("🧾 Send Settlement")
        with st.container(border=True):
            s_to = st.selectbox("I am paying back:", [t for t in target_names if t != target_names[0]])
            s_amt = st.number_input("Amount (₹)", min_value=0.01, key="s_amt")
            if st.button("Send Settlement"):
                request_settlement(me_username, target_mapping[s_to], s_amt)
                st.success("Sent for confirmation!")
                st.rerun()

# ==========================================
# TAB: FRIENDS & NETWORK
# ==========================================
with tab_friends:
    st.header("Manage Friends")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Add a Friend")
        with st.container(border=True):
            nf_name = st.text_input("Display Name", placeholder="Alice")
            nf_user = st.text_input("Global Username (Required)", placeholder="alice_123")
            if st.button("Add Friend", use_container_width=True):
                if nf_name.strip() and nf_user.strip():
                    succ, msg = add_friend(me_id, nf_name.strip(), nf_user.strip())
                    if succ: st.rerun()
                    else: st.error(msg)
                else:
                    st.error("Both a Display Name and a Global Username are strictly required!")
                    
    with col2:
        st.subheader("Your Network")
        if not active_friends:
            st.info("You haven't added anyone yet.")
        else:
            for f in active_friends:
                fc1, fc2 = st.columns([3, 1])
                conn_lbl = f"<span style='color:green'>Global Account: @{f['linked_username']}</span>" if f.get('linked_username') else "<span style='color:gray'>Local Ghost Node</span>"
                fc1.markdown(f"**{f['name']}** <br> {conn_lbl}", unsafe_allow_html=True)
                if fc2.button("Unfollow", key=f"unf_{f['id']}"):
                    remove_friend(me_id, f['id'])
                    st.rerun()
