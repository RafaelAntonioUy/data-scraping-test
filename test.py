from googlesearch import search
import time

# Your list of codes
codes = [
    "40146", "40153", "4022501", "40236", "4026100", "40291", "40340", "40352-05", 
    "40370", "40373", "40391-14", "40393", "40398", "40402", "40500", "40501-04", 
    "40501-05", "40521-25", "40541-02", "40541-14", "40561", "40581", "40673", 
    "40676", "40710", "40712", "40735", "40737-00", "4109", "4112-07", "41270-00", 
    "41520", "43125-07", "43134-03", "43134-07", "4350-03", "4350-06", "43501", 
    "4355-06", "4358-06", "4360-06", "4364", "4370-06", "43901-03", "43903-02", 
    "43903-03", "43903-42", "43905", "43907-03", "43907-42", "43911/401", "43925", 
    "43933-07", "43965", "4416-13", "4420-06", "4421-03", "4421-06", "45493", 
    "4550-02", "4550-03", "4709-06", "4712-01", "4712-06", "4900-13", "49500-07", 
    "49501-07", "49503-07", "49504-07", "49505-07", "509-01", "509-02", "509-03", 
    "509-06", "5216", "5506", "5509", "5517-07", "5517-10", "5517-48", "5536", 
    "5540", "5649-07", "5650-07", "5651-07", "601029", "608216", "609106", "6630", 
    "6640", "6963", "6966", "7208", "7734", "7738", "7739", "8004", "8113", 
    "8622-03", "ADD4-01", "ADSC07", "C2236-14", "C2236H-14", "C32P1-14", "CH13", 
    "CH14", "CH27", "CM1030-02", "CM1030-03", "CM1033P", "CM1037", "CT1216-06", 
    "GR09RS", "GR10", "HL7237", "HL8285B", "HLA20", "IG222", "LD1001GA", "LD111VC", 
    "LD235GA", "LD333FA", "LD350N-01", "LD4CC", "PC140N", "PC160N", "PC301GA-03", 
    "PC600N", "PC650", "PC660", "PCD205-56", "PCD205-59", "PCD211-56", "PCD308-03", 
    "PCD500-56", "PCD500-59", "PCD596-56", "PCD700-56", "PLQ-09", "PS501N", 
    "PS601N", "PS701B", "PS802", "PSD13", "PSD21CH", "RG25-1", "RG25-2", "RG25-4", 
    "RG9-3", "S280-02", "S280-03", "S280-42", "S280-69", "S282-02", "S285-02", 
    "S285-03", "S285-14", "S285-42", "S285-52", "S285-69", "S286-03", "S286-42", 
    "S287-02", "S287-03", "S287-42", "SC26", "SC29", "SC38", "ST1532", "ST1544", 
    "ST1556", "ST1568", "ST1573", "ST1587", "ST1629", "ST1630", "TC1826N", "WP26", 
    "XT10000-01", "XT10001GA-02", "XT2500-08", "XT2500-25", "XT2500-59", 
    "XT2500-95", "XT2550GA-02", "XT2550LA-03", "XT5000-59"
]

results = []

print(f"Starting extraction for {len(codes)} codes...")
print("This will take about 8-10 minutes to safely avoid Google rate limits.\n")

for code in codes:
    query = f'site:carlislefsp.com "{code}"'
    found_url = "No result found"
    
    try:
        # Search Google and grab the first URL
        for url in search(query, num_results=1):
            if "carlislefsp.com" in url:
                found_url = url
                break
    except Exception as e:
        found_url = f"Error: {e}"
        
    print(f"[{code}] -> {found_url}")
    results.append(f"{code}\t{found_url}")
    
    # 3-second pause to prevent Google from blocking your IP
    time.sleep(3)

# Save the final list to a text file
with open("carlisle_final_links.txt", "w") as file:
    for line in results:
        file.write(f"{line}\n")
        
print("\nSuccess! All links have been saved to 'carlisle_final_links.txt'.")