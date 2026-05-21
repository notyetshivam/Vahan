import os
import glob
import re
import pandas as pd

# 1. Define Paths
folder_path = r"C:\Users\inter\Downloads\Pepsico Stuff\vahan_rto_data"
output_file = os.path.join(folder_path, "Consolidated_RTO_List.xlsx")

# 2. Define State to Region Mapping
# Note: title() capitalizes 'And', so keys match the title-cased file names.
region_map = {
    # North
    'Jammu And Kashmir': 'North', 'Ladakh': 'North', 'Himachal Pradesh': 'North', 
    'Punjab': 'North', 'Chandigarh': 'North', 'Uttarakhand': 'North', 
    'Haryana': 'North', 'Delhi': 'North', 'Uttar Pradesh': 'North', 'Rajasthan': 'North',
    # South
    'Andhra Pradesh': 'South', 'Karnataka': 'South', 'Kerala': 'South', 
    'Tamil Nadu': 'South', 'Telangana': 'South', 'Puducherry': 'South', 
    'Lakshadweep': 'South', 'Andaman And Nicobar': 'South',
    # East
    'Bihar': 'East', 'Jharkhand': 'East', 'Odisha': 'East', 'West Bengal': 'East',
    # West
    'Gujarat': 'West', 'Maharashtra': 'West', 'Goa': 'West', 
    'Dadra And Nagar Haveli': 'West', 'Daman And Diu': 'West', 
    'Dadra And Nagar Haveli And Daman And Diu': 'West',
    # Central (Categorized as Central by standard, but you can change to North/West if needed)
    'Madhya Pradesh': 'Central', 'Chhattisgarh': 'Central',
    # North-East
    'Assam': 'North-East', 'Arunachal Pradesh': 'North-East', 'Manipur': 'North-East', 
    'Meghalaya': 'North-East', 'Mizoram': 'North-East', 'Nagaland': 'North-East', 
    'Sikkim': 'North-East', 'Tripura': 'North-East'
}

all_rto_data = []

# 3. Find all Excel files in the directory
file_pattern = os.path.join(folder_path, "*.xlsx")
excel_files = glob.glob(file_pattern)

print(f"Found {len(excel_files)} files. Starting extraction...")

for file in excel_files:
    filename = os.path.basename(file)
    
    # 4. Extract State Name from filename (everything before '_Rto_')
    # Using re.split with IGNORECASE handles both '_RTO_' and '_Rto_'
    state_part = re.split(r'_Rto_', filename, flags=re.IGNORECASE)[0]
    state_name = state_part.replace("_", " ").title()
    
    # 5. Map the Region
    region = region_map.get(state_name, 'Unknown')
    
    try:
        # 6. Dynamically find the header row
        # Read the first 15 rows to locate the 'Rto' column to handle shifting headers
        df_temp = pd.read_excel(file, header=None, nrows=15)
        header_row_idx = -1
        rto_col_idx = -1
        
        for i, row in df_temp.iterrows():
            for j, val in enumerate(row):
                if str(val).strip().lower() == 'rto':
                    header_row_idx = i
                    rto_col_idx = j
                    break
            if rto_col_idx != -1:
                break
                
        if header_row_idx != -1:
            # Re-read the file using the correct header row
            df = pd.read_excel(file, header=header_row_idx)
            
            # The exact column name might have padding (e.g., '     Rto     ')
            rto_col_name = df.columns[rto_col_idx]
            
            # Extract unique RTOs and drop NaN values
            rtos = df[rto_col_name].dropna().unique().tolist()
            
            for rto in rtos:
                rto_clean = str(rto).strip()
                # Exclude blank rows and the 'TOTAL' summary row at the bottom
                if rto_clean.upper() != 'TOTAL' and rto_clean != '':
                    all_rto_data.append({
                        'RTO Name': rto_clean,
                        'State Name': state_name,
                        'Region': region
                    })
        else:
            print(f"Warning: 'Rto' column could not be found in {filename}")
            
    except Exception as e:
        print(f"Error processing {filename}: {e}")

# 7. Consolidate and Remove Duplicates
print("Consolidating data and removing duplicates...")
final_df = pd.DataFrame(all_rto_data)
final_df.drop_duplicates(subset=['RTO Name', 'State Name'], inplace=True)

# 8. Export to Excel
final_df.to_excel(output_file, index=False)
print(f"Success! Extracted {len(final_df)} unique RTOs.")
print(f"File saved to: {output_file}")