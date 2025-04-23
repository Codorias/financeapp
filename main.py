import streamlit as st
import pandas as pd
import plotly.express as px
import json 
import os

st.set_page_config(page_title="Day to day finance app", page_icon="💵", layout="wide")

category_file = "categories.json"

# Initialize session state variables
if "categories" not in st.session_state:
    st.session_state.categories = {
        "Uncategorized": []
    }

if "categorized_transactions" not in st.session_state:
    st.session_state.categorized_transactions = None

# Load categories from file if it exists
if os.path.exists(category_file):
    with open(category_file, "r") as f:
        st.session_state.categories = json.load(f)

def save_categories():
    with open(category_file, "w") as f:
        json.dump(st.session_state.categories, f)

def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue
        
        lowered_keywords = [keyword.lower().strip() for keyword in keywords]

        for idx, row in df.iterrows():
            details = row["Details"].lower().strip()
            if details in lowered_keywords:
                df.at[idx, "Category"] = category
    return df

def load_transactions(file):
    try:
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        
        # Handle Amount column more robustly
        if df["Amount"].dtype == object:  # if amount is string
            # Remove any commas and convert to float
            df["Amount"] = df["Amount"].replace({',': ''}, regex=True).astype(float)
        else:
            # If it's already numeric, just ensure it's float
            df["Amount"] = df["Amount"].astype(float)

        # Convert date with error handling
        try:
            # Try DD/MM/YYYY format first
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y")
        except ValueError:
            try:
                # Try the original format as fallback
                df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")
            except ValueError:
                # If both specific formats fail, try automatic parsing with dayfirst=True
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)

        # If we have previously categorized transactions, use those categories
        if st.session_state.categorized_transactions is not None:
            # Merge the categories from previous categorization
            df = df.merge(
                st.session_state.categorized_transactions[["Details", "Category"]], 
                on="Details", 
                how="left"
            )
            # Fill any missing categories with "Uncategorized"
            df["Category"] = df["Category"].fillna("Uncategorized")
        else:
            df = categorize_transactions(df)

        return df
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def add_keyword_to_category(category, keyword):
    keyword = keyword.strip()
    if keyword and keyword not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True
    
    return False


def main():
    st.title("Simple Finance Dashboard")

    uploaded_file = st.file_uploader("Upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)

        if df is not None:
            debits_df = df[df["Debit/Credit"] == "Debit"].copy() 
            credits_df = df[df["Debit/Credit"] == "Credit"].copy()

            st.session_state.debits_df = debits_df.copy()

            tab1, tab2 = st.tabs(["Expenses (Debit)", "Payments (Credits)"])
            with tab1:
                new_category = st.text_input("New category name")
                add_button = st.button("Add Category")

                if add_button and new_category:
                    if new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.rerun()

                # Add visualizations before the data editor
                col1, col2 = st.columns(2)
                
                with col1:
                    # Pie chart of expenses by category
                    category_expenses = st.session_state.debits_df.groupby('Category')['Amount'].sum().reset_index()
                    fig_pie = px.pie(
                        category_expenses,
                        values='Amount',
                        names='Category',
                        title='Expenses by Category',
                        hole=0.4
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col2:
                    # Bar chart of monthly expenses
                    monthly_expenses = st.session_state.debits_df.groupby(
                        st.session_state.debits_df['Date'].dt.strftime('%Y-%m')
                    )['Amount'].sum().reset_index()
                    monthly_expenses.columns = ['Month', 'Amount']
                    
                    fig_bar = px.bar(
                        monthly_expenses,
                        x='Month',
                        y='Amount',
                        title='Monthly Expenses Trend',
                        labels={'Amount': 'Total Expenses (BOB)', 'Month': 'Month'}
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)

                # Add a line chart showing daily expense trends
                daily_expenses = st.session_state.debits_df.groupby('Date')['Amount'].sum().reset_index()
                fig_line = px.line(
                    daily_expenses,
                    x='Date',
                    y='Amount',
                    title='Daily Expense Trend',
                    labels={'Amount': 'Daily Expenses (BOB)', 'Date': 'Date'}
                )
                st.plotly_chart(fig_line, use_container_width=True)

                # Add summary statistics
                col3, col4, col5 = st.columns(3)
                with col3:
                    total_expenses = st.session_state.debits_df['Amount'].sum()
                    st.metric("Total Expenses", f"{total_expenses:,.2f} BOB")
                
                with col4:
                    avg_daily_expense = st.session_state.debits_df.groupby('Date')['Amount'].sum().mean()
                    st.metric("Average Daily Expense", f"{avg_daily_expense:,.2f} BOB")
                
                with col5:
                    num_transactions = len(st.session_state.debits_df)
                    st.metric("Number of Transactions", f"{num_transactions:,}")

                st.subheader("Your Expenses")
                edited_df = st.data_editor(
                    st.session_state.debits_df[["Date", "Details", "Amount", "Category"]],   
                    column_config={
                        "Date": st.column_config.DateColumn(
                            "Date",
                            format="DD/MM/YYYY"
                        ),
                        "Amount": st.column_config.NumberColumn("Amount", format="%.2f BOB"),
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            options=list(st.session_state.categories.keys())
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="category_editor"
                )

                save_button = st.button("Apply Changes", type="primary")
                if save_button:
                    # Update categories and transactions
                    for idx, row in edited_df.iterrows():
                        new_category = row["Category"]
                        old_category = st.session_state.debits_df.at[idx, "Category"]
                        
                        # Only process if category has changed
                        if new_category != old_category:
                            details = row["Details"]
                            # Update the transaction's category
                            st.session_state.debits_df.at[idx, "Category"] = new_category
                            # Add the transaction details as a keyword for the new category
                            add_keyword_to_category(new_category, details)
                    
                    # Save the updated categories to file
                    save_categories()
                    # Save the categorized transactions for future use
                    st.session_state.categorized_transactions = st.session_state.debits_df
                    st.success("Changes saved successfully!")
            with tab2:
                st.subheader("Payments Summary")
                
                # Summary metrics in columns
                col1, col2 = st.columns(2)
                with col1:
                    total_payments = credits_df["Amount"].sum()
                    st.metric("Total Payments", f"{total_payments:,.2f} BOB")
                
                with col2:
                    avg_payment = credits_df["Amount"].mean()
                    st.metric("Average Payment", f"{avg_payment:,.2f} BOB")

                # Monthly payments trend
                monthly_payments = credits_df.groupby(
                    credits_df['Date'].dt.strftime('%Y-%m')
                )['Amount'].sum().reset_index()
                monthly_payments.columns = ['Month', 'Amount']
                
                fig_payments = px.bar(
                    monthly_payments,
                    x='Month',
                    y='Amount',
                    title='Monthly Payments Trend',
                    labels={'Amount': 'Total Payments (BOB)', 'Month': 'Month'}
                )
                fig_payments.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_payments, use_container_width=True)

                # Display the transactions table
                st.subheader("Payment Transactions")
                st.write(credits_df)


main()