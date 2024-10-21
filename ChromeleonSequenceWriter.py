import os
import pandas as pd
import argparse
from fpdf import FPDF
import matplotlib.colors as mcolors
import requests
import warnings
import matplotlib.pyplot as plt

"""
Chromeleon Sample Sequence Writer

Author: Mink Sieders, 24/09/2024 09:21 AM

Changelog:
V5.1 Ensured standards (samples with id beginning with STD) are ran between samples controlled 
with an x number of times throughout the run. 
V5.2 Added a sample tray layout overview as part of the output in .pdf format.
V5.3 Allows user to insert a different instrument method for samples stored in 1.5 mL vials
V5.4 Outputs will be added in a user defined output, or default to: /MANIFEST_FOLDER_Output
V5.5 Added some options for user-input to prevent accidentally writing over pre-existing folders 
V6.0 Setupenv flag: setup an environment with empty files which can be used in the script. 
V6.0 Adds an option to leave empty spaces on trays denoted by beginning with "OMIT{rest_of_sample_name}". 
V6.1 Also adds a technical replicate number for standard samples (i.e., STD0uM.TR1 and STD0uM.TR2 etc.)

FUTURE:
V7 Ensures when there are no vial samples all trays can be used for plates, and vice versa (no plates there should
always be available vials). 
V7 Add another flag where the script enters an editor for plate or vial manifest files. 

Input:
- A manifest folder containing:
  - A 'plates' subfolder with .xlsx files for 96-well plate designs
  - A 'vials.xlsx' file for 1.5 mL vial samples

Usage:
- Run with --help for usage instructions
- Use --setup_env True to create a mock/template manifest folder environment

Note: This script is flexible and can handle various plate and vial configurations. Users should not change the 
'vials.xlsx' filename, but plate manifest files in the 'plates' folder can have any name.

Author: Mink Sieders
Version: 6.1
Last Updated: 21/10/2024
"""


# Function to read and process the vials.xlsx file
def process_vial_manifest(file_path, trays_for_vials):
    vials_df = pd.read_excel(file_path, header=None)
    vials_df.columns = ["Sample"]
    vials_df["Location"] = "VIAL"

    # Initialize the Tray and Well columns
    vials_df["Tray"] = None
    vials_df["Well"] = None

    # Number of rows in vials_df
    num_rows = len(vials_df)

    # Define the vial tray map positions (5 rows × 8 columns)
    rows = ["A", "B", "C", "D", "E"]  # Row labels from bottom to top
    cols = [str(i) for i in range(1, 9)]  # Column numbers from 1 to 8
    positions = [f"{row}{col}" for row in rows for col in cols]  # Generate all positions (total of 40)

    # Iterate over the vials_df in chunks of 40
    for i in range(0, num_rows, 40):
        tray_index = (i // 40) % len(trays_for_vials)  # Calculate the tray index based on the chunk
        tray_name = trays_for_vials[tray_index]  # Get the current tray

        # Assign the tray to the current chunk of vials
        vials_df.loc[i:i + 39, "Tray"] = tray_name  # Assign tray to the next 40 vials (or remaining ones)

        # Assign positions to the Well column
        for j in range(min(40, num_rows - i)):  # Ensure we don"t go out of bounds
            vials_df.at[i + j, "Well"] = positions[j]  # Assign the corresponding position
    return vials_df


# Function to process the plate .xlsx files
def process_plate_manifest(plate_file, tray):
    plate_df = pd.read_excel(plate_file, header=0, index_col=0)
    plate_data = []

    for row in plate_df.index:
        for col in plate_df.columns:
            sample_id = plate_df.loc[row, col]
            if isinstance(sample_id, str):
                well_position = f"{row}{col}"
                plate_data.append({"Sample": sample_id, "Well": well_position, "Plate_File": os.path.basename(plate_file), "Tray": tray})

    return pd.DataFrame(plate_data)


# Determine if sample gets technical replicates
def get_technical_replicates(sample_name, tr_num):
    if pd.isna(sample_name):
        return tr_num
    s = sample_name.lower()
    if s.startswith(("std", "standard")):
        return 1  # 5 replicates for standard samples
    else:
        return tr_num  # Default to 2 replicates for other samples


# Reformat sample names for better alphabetically sorting later on in program
def format_sample_name(sample_name, replicate_number):
    def starts_with_std_or_standard(s):
        # Convert the string to lowercase
        if pd.isna(s):
            return False
        lower_s = s.lower()
        # Check if it starts with "std" or "standard"
        return lower_s.startswith("std") or lower_s.startswith("standard")

    if starts_with_std_or_standard(sample_name):
        # Handle standard samples
        parts = sample_name.split(".")
        prefix = "".join([c for c in parts[0] if not c.isdigit()])
        number = "".join([c for c in parts[0] if c.isdigit()])
        formatted_name = f"{prefix}{number}.TR{replicate_number}"
        return formatted_name
    else:
        # Handle non-standard samples
        try:
            # Split the sample name at the first period
            parts = sample_name.split(".")

            # Extract the number part (the first part before the period)
            prefix = "".join([c for c in parts[0] if not c.isdigit()])
            number = "".join([c for c in parts[0] if c.isdigit()])

            # Pad the number with leading zeros to make it 5 digits long
            formatted_number = f"{int(number):05d}"

            # Rebuild the sample name with the padded number
            formatted_name = f"{prefix}{formatted_number}." + ".".join(parts[1:] if len(parts) > 1 else parts)

            # Append technical replicate information
            if replicate_number > 0:
                formatted_name += f".TR{replicate_number}"

            return formatted_name
        except Exception as e:
            print(f"Error formatting sample name {sample_name}: {e}")
            return sample_name  # Return unmodified in case of error

# Insert repitition of STD samples from vials throughout program
def std_replcicates(df, x):
    # Step 1: Identify rows where the "Name" column contains "STD"
    std_rows = df[df["Name"].str.contains("STD", na=False)]

    # Calculate the number of intervals to insert the rows
    interval = len(df) // x

    # Step 2: Loop to insert these rows `x` times throughout the dataframe
    insert_positions = [0] + [(i + 1) * interval for i in range(x-1)]

    for i, pos in enumerate(insert_positions):
        # Insert the STD rows at the calculated positions
        df = pd.concat([df.iloc[:pos], std_rows, df.iloc[pos:]]).reset_index(drop=True)

    return df


# Function to generate the HPLC output file
def generate_HPLC_program(sorted_samples, instrument_method, injection_volume, output_folder, rep_num_std, tech_rep_num):
    # Filter out samples that are marked with "OMIT"
    filtered_samples = sorted_samples[~sorted_samples["Sample"].str.startswith("OMIT", na=False)]

    HPLC_data = []

    for idx, sample in filtered_samples.iterrows():
        num_replicates = get_technical_replicates(sample["Sample"], tech_rep_num)  # Get the number of replicates

        for replicate_number in range(num_replicates):
            well = sample["Well"]  # Use the well position directly from the sample
            tray_selected = sample["Tray"]  # Get the tray directly from the sample data

            # Generate the position code (e.g., RA1, GB2)
            if sample["Location"] == "VIAL":
                # For vials, use the tray selected (assumed to be Red for vials)
                position_code = f"{sample["Tray"]}{well[0]}{well[1]}"  # Format: RA1, RB2, etc.
            else:
                # For plates: Use the well information directly from the sample data
                well_number = int(well[1:])  # Extract the column number
                position_code = f"{tray_selected[0]}{well[0]}{well_number}"  # Format: PA1, PB12, etc.

            mtd = instrument_method
            if args.vial_instrument_method != None:
                if sample["Location"] == "VIAL":
                    mtd = args.vial_instrument_method

            # Append to the HPLC data
            HPLC_data.append({
                "ED_1": "None",
                "Name": format_sample_name(sample["Sample"], replicate_number + 1),
                "Type": "Unknown",
                "Level": "",
                "Position": position_code,
                "Volume [ul]": injection_volume,
                "Instrument Method": mtd
            })

    # Convert HPLC_data into a DataFrame and save as a tab-separated file
    HPLC_df = pd.DataFrame(HPLC_data,
                           columns=["ED_1", "Name", "Type", "Level", "Position", "Volume [ul]", "Instrument Method"])
    HPLC_df = HPLC_df.sort_values(by="Name").reset_index(drop=True)

    HPLC_df_final = std_replcicates(HPLC_df, x=rep_num_std)

    HPLC_df_final.to_csv(os.path.join(output_folder, "sample_sequence_"+folder+".txt"), index=False, sep="\t")


# Function to generate vial layout image
def generate_vial_layout_image(vials_mapping_dataframe):
    def create_tray_image(tray_df, tray_id, image_file, part):
        fig, ax = plt.subplots(figsize=(6, 4))  # Adjust size as needed

        # Define rows and columns for a 5x8 tray
        rows = ["A", "B", "C", "D", "E"]
        cols = [str(i) for i in range(1, 9)]

        # Color based on tray type
        tray_colors = {"B": "lightblue", "R": "lightcoral", "G": "lightgreen"}
        tray_color = tray_colors.get(tray_id, "lightgrey")  # Default to grey if tray type is unknown

        # Create a dictionary for quick lookup of samples by well position
        vial_data = dict(zip(tray_df["Well"], tray_df["Sample"]))

        # Plot each vial position and label it with the sample name
        for i, row in enumerate(rows):
            for j, col in enumerate(cols):
                pos = f"{row}{col}"  # Generate the well position
                sample = vial_data.get(pos, "")  # Get the sample name or empty if none
                # Draw the well as a square
                ax.add_patch(plt.Rectangle((j, i), 1, 1, edgecolor="black", facecolor=tray_color))

                # Add sample name (or leave blank) to the center of the well
                ax.text(j + 0.5, i + 0.5, sample, va="center", ha="center", fontsize=6)

        # Set axis limits and labels
        ax.set_xlim(0, len(cols))
        ax.set_ylim(0, len(rows))
        ax.set_xticks([i + 0.5 for i in range(len(cols))])
        ax.set_xticklabels(cols)
        ax.set_yticks([i + 0.5 for i in range(len(rows))])
        ax.set_yticklabels(rows)

        # Invert the y-axis to make "A" at the top and "E" at the bottom
        ax.invert_yaxis()

        # Hide axis borders
        ax.set_aspect("equal")
        ax.axis("off")

        # Set title for the tray
        ax.set_title(f"Tray {tray_id} Part {part}", fontsize=16)

        # Save the image
        plt.savefig(image_file, dpi=300)
        plt.close()

    trays = vials_mapping_dataframe["Tray"].unique()

    # For each unique tray, we create a new image
    for tray in trays:
        tray_df = vials_mapping_dataframe[vials_mapping_dataframe["Tray"] == tray]

        # Determine how many 5x8 trays we need for this specific tray"s samples
        num_samples = len(tray_df)
        num_trays_needed = (num_samples // 40) + 1  # Each tray holds 40 samples, need additional tray if overflow

        for i in range(num_trays_needed):
            # Get the current batch of samples for this tray (up to 40 per tray)
            batch_df = tray_df.iloc[i * 40:(i + 1) * 40]

            # File name for each image based on the tray and part number if needed
            image_file = f"Tray_{tray}_Part_{i + 1}.png"
            image_file = os.path.join(tmp, image_file)
            part_tray = i + 1
            # Create the tray image
            create_tray_image(batch_df, tray, image_file, part_tray)


# Function to create the PDF
def generate_pdf(output_pdf, tray_mapping):
    pdf = FPDF()

    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Arial", "B", 16)
    pdf.multi_cell(0, 10, "Procedure for loading HPLC samples in autosampler", align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)  # Regular text, size 12
    pdf.multi_cell(0, 10, "DO NOT FORGET TO SET THE TRAY TYPE IN THE AUTOSAMPLER!", align="C")
    pdf.ln(10)

    # Define the image URL and local filename
    image_url = "https://preview.redd.it/prfhf0nxhika1.jpg?auto=webp&s=d8d8572b8c6835d8b1436b175f3e433484e4245b"
    image_filename = "hplc_sample_image.jpg"

    # Download the image
    def download_image(url, filename):
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
        return False

    # Download the image
    if download_image(image_url, image_filename):
        # Get page width
        page_width = pdf.w
        image_width = 120  # Set the desired width of the image

        # Calculate the x position to center the image
        x_position = (page_width - image_width) / 2

        # Add the image to the PDF centered and smaller
        pdf.image(image_filename, x=x_position, w=image_width)  # Use calculated x and desired width
        pdf.ln(10)  # Add space below the image

    # Optional: Remove the downloaded image after adding to PDF
    if os.path.exists(image_filename):
        os.remove(image_filename)

    # Find all .png files in the current directory
    image_files = [file for file in os.listdir(tmp) if file.endswith(".png")]

    # Add each image to the PDF
    for img_file in image_files:
        img_file = os.path.join(tmp,img_file)
        pdf.add_page()  # Add a new page for each image
        pdf.ln(10)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, f"Vial Trays Layout", ln=True, align="C")  # Title for each image

        # Add the image
        pdf.image(img_file, x=10, y=30, w=180)  # Adjust "w" as needed to fit the page
        pdf.ln(110)  # Move below the image

    # Add tray mapping text at the end of the PDF
    tray_colors = {"B": "lightblue", "R": "lightcoral", "G": "lightgreen"}
    tray_colors_rgb = {key: tuple(int(255 * c) for c in mcolors.to_rgb(color)) for key, color in tray_colors.items()}

    pdf.add_page()  # Add a new page for the tray mapping explanation
    pdf.ln(10)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "96-Well Plate Trays Loading Protocol", ln=True, align="C")
    pdf.ln(10)  # Add space before listing trays
    pdf.set_font("Arial","", 12)
    for plate, color in tray_mapping.items():
        pdf.set_left_margin(20)  # Adjust this value to your desired indentation
        pdf.cell(80, 10, f"96-Well plate {plate} should be loaded in: ", ln=False)
        r, g, b = tray_colors_rgb[color]
        pdf.set_text_color(r, g, b)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(80, 10, f" Tray {color}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 12)
        pdf.set_left_margin(10)  # Reset to default value after if needed

    # Output the PDF to a file
    pdf.output(output_pdf)


# Function to process all files and generate the HPLC program
def main(folder, instrument_method, injection_volume, out_fol, plate_tray_number, std_rep_num, available_trays, technical_replicates_samples):
    vials_file = os.path.join(folder, "vials.xlsx")
    plates_folder = os.path.join(folder, "plates")
    all_trays = available_trays
    trays_for_plates = all_trays[0:plate_tray_number]
    trays_for_vials = all_trays[plate_tray_number:]

    std_rep = std_rep_num - 1  # one is already implied by simply adding the samples into existence

    # Process vials.xlsx
    if os.path.exists(vials_file):
        vials_data = process_vial_manifest(vials_file, trays_for_vials)
    else:
        warnings.warn("No vials.xlsx file found! Will assume the user does not require any samples in vial trays")
        vials_data = pd.DataFrame(columns=["Sample", "Location"])

    # Process plate files
    if os.path.exists(plates_folder):
        plate_files = [f for f in os.listdir(plates_folder) if f.endswith(".xlsx")]

        all_plate_data_list = []
        tray_index = 0  # Initialize tray index

        # Process each plate file and append the result to the list
        for plate_file in plate_files:
            tray = trays_for_plates[tray_index]
            plate_data = process_plate_manifest(os.path.join(plates_folder, plate_file), tray)
            all_plate_data_list.append(plate_data)
            tray_index = (tray_index + 1) % len(trays_for_plates)
        all_plate_data = pd.concat(all_plate_data_list, ignore_index=True)
        all_plate_data["Location"] = "PLATE"
    else:
        warnings.warn("No plates folder found! Will assume user does not require 96-well trays.")
        all_plate_data = pd.DataFrame(columns=["Sample", "Well", "Plate_File", "Location"])

    # Concatenate vials and plate data
    all_samples = pd.concat([vials_data, all_plate_data], ignore_index=True)

    # Apply the formatting to ensure sample names are correctly padded
    all_samples["Sample"] = all_samples["Sample"].apply(lambda x: format_sample_name(x, 0))  # Initially format without replicate

    # Generate HPLC program with sorted samples
    generate_HPLC_program(all_samples, instrument_method, injection_volume, out_fol, std_rep, technical_replicates_samples)

    # Retrieve tray mapping 96-well plates
    unique_combinations = all_plate_data[["Plate_File", "Tray"]].drop_duplicates()
    tray_mapping = {}
    for _, row in unique_combinations.iterrows():
        plate_file_name = row["Plate_File"].replace(".xlsx", "")
        tray_mapping[plate_file_name] = row["Tray"]

    # Retrieve vial mapping normal 1.5 mL vials
    vial_data_filtered = vials_data[vials_data["Location"] == "VIAL"]

    # Create a new DataFrame with "Well", "Sample", and "Tray" columns
    vial_mapping = vial_data_filtered[["Well", "Sample", "Tray"]].reset_index(drop=True)
    generate_vial_layout_image(vial_mapping)

    # Generate the PDF with the vial layout image and tray mapping
    generate_pdf(os.path.join(out_fol,"AS_loading_protocol.pdf"), tray_mapping)

    print("\nAll outputs generated.")


def main_setup_env():
    def create_vials_excel(file_path):
        vials_data = [[f'VIAL_EXAMPLE_{i}.R1.T0'] for i in range(1, 6)]  # VIAL_EXAMPLE_1 to VIAL_EXAMPLE_5
        std_data = [[f'STD_EXAMPLE_{i}.R1.T0'] for i in range(1, 6)]  # STD_EXAMPLE_1 to STD_EXAMPLE_5
        omit_data = [[f'OMIT_EXAMPLE_{i}.R1.T0'] for i in range(1, 6)]  # STD_EXAMPLE_1 to STD_EXAMPLE_5
        combined_data = std_data + vials_data + omit_data
        df = pd.DataFrame(combined_data)
        df.to_excel(file_path, index=False, header=False)

    def create_plate_excel(file_path, plate_name):
        # Create an Excel file with the layout described and replace the sample names with EXAMPLE_{A/B/C}_Well_{1-through-96}
        columns = list(range(1, 13))  # 12 columns
        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']  # 8 rows

        # Initialize an empty dictionary for the plate data
        data = {}

        # Well numbering starts from 1 to 96 row-wise
        well_number = 1
        for row in rows:
            data[row] = [f'EXAMPLE_{plate_name}_Well_{well_number + i}.R1.T0' for i in range(12)]
            well_number += 12  # Move to the next set of 12 wells for the next row

        # Create the DataFrame and save it as an Excel file
        df = pd.DataFrame(data, index=columns).transpose()
        df.to_excel(file_path, index=True)

    # Ask the user whether to create the default folder in the current directory
    create_default = input(
        "Do you want to create the template manifest folder in the current directory with the default name 'template_manifest_folder'? (y/n): ").strip().lower()

    if create_default == 'y':
        manifest_folder = 'template_manifest_folder'
    else:
        # Ask the user for a custom folder path
        manifest_folder = input("Please provide the desired template manifest folder path: ").strip().rstrip('/')

    # Create the manifest template folder
    os.makedirs(manifest_folder, exist_ok=True)

    # Create the 'vials.xlsx' file
    vials_file_path = os.path.join(manifest_folder, 'vials.xlsx')
    create_vials_excel(vials_file_path)

    # Create the 'plates' folder
    plates_folder = os.path.join(manifest_folder, 'plates')
    os.makedirs(plates_folder, exist_ok=True)

    # Create the three plate Excel files
    for plate in ['A', 'B', 'C']:
        plate_file_path = os.path.join(plates_folder, f'PLATE_EXAMPLE_{plate}.xlsx')
        create_plate_excel(plate_file_path, plate)

    # Finish with a message
    print(f"Created template manifest folder environment at location: {os.path.abspath(manifest_folder)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HPLC program from sample data.")
    parser.add_argument("--folder", help="Folder containing vials.xlsx and plates folder.", default=None)
    parser.add_argument("--instrument_method", default=None,
                        help="Instrument method used for all samples (default: MS_Catecholamine_Iso_col25) or only "
                             "for 96-well samples when --vial_instrument_method is specified")
    parser.add_argument("--injection_volume", default=None, type=float, help="Injection volume in ul "
                                                                             "(default: 25.0)")
    parser.add_argument("--output", default=None,
                        help="Output HPLC program file name (default: HPLC_program.txt)")
    parser.add_argument("--plate_tray_number", default=None, type=int,
                        help="Number of trays allocated for plates (default: 2)")
    parser.add_argument("--standard_replicate_number", default=None, type=int,
                        help="Number of times the standard series is ran, defaults at 5 (must be at least 2)")
    parser.add_argument("--trays", default=None, type=list,
                        help="List of colorcodes for each respective sampling tray available in the HPLC autosampler, "
                             "defaults to Red (R) Green (G) and blue (B) | or ['R', 'G', 'B']")
    parser.add_argument("--technical_replicates_samples", default=None, type=int,
                        help="Number of times each sample is injected into HPLC (technical replicates, default = 2)")
    parser.add_argument("--vial_instrument_method", default=None, type=str,
                        help="Used to specify a method for vial samples that differs from the main instrument_method")
    parser.add_argument("--setup_env", default=False, type=bool,
                        help="Omits main script, creates an environment folder with 96-well plate template"
                             "files and the main 'vials' excel sheet. ")
    args = parser.parse_args()

    if args.setup_env == True:
        main_setup_env()

    else:
        if args.folder == None:
            raise Exception(f"Please specify a manifest folder where samples are located")
        else:
            folder = args.folder.rstrip('/')
            if not os.path.exists(folder):
                raise Exception(f"Manifest folder '{folder}' does not exist")

        statusTmpDeletion = 999
        current_directory = os.getcwd()
        if args.output == None:
            output_folder = folder + "_output"

            print(f"\nNo output folder is specified. Defaulting to output folder: {output_folder}")

            output = os.path.join(current_directory, output_folder)

        else:
            output_folder = args.output
            output = os.path.join(current_directory, output_folder)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"Created output folder: {output_folder}")

        else:
            user_input = input(
                f"\nOutput folder already exists at {output_folder}. Do you want to continue using this folder and "
                f"potentially overwrite existing files? (y/n): ")

            if user_input.lower() == "y":
                print(f"\nContinuing with existing folder: {output_folder}")
                statusTmpDeletion = 36

            elif user_input.lower() == "n":
                new_folder_name = input("\nPlease enter a new folder name: ")
                output_folder = new_folder_name + "_HPLC_sequence"
                output = os.path.join(current_directory, output_folder)
                os.makedirs(output)  # Create the new folder
                print(f"\nCreated output folder: {output_folder}")
            else:
                print("\nInvalid input. Exiting.")
                exit(1)  # Exit if input is not valid

        tmp = os.path.join(output, "tmp")
        if not os.path.exists(tmp):
            os.makedirs(tmp)
        else:
            if statusTmpDeletion == 36:
                try:
                    os.rmdir(tmp)
                except FileNotFoundError:
                    print(f"Error: {e}")
                except OSError as e:
                    print(f"Error: {e}")

        if args.instrument_method == None:
            method = "MS_Catecholamine_Iso_col25"
            print(f"\nUsing default instrument method name: {method}")
        else:
            method = args.instrument_method

        if args.injection_volume == None:
            inj_vol = 25.0
            print(f"Using default injection volume: {inj_vol}")
        else:
            inj_vol = args.injection_volume

        if args.plate_tray_number == None:
            trays96 = 2
            print(f"Using default 96-well plate tray number: {trays96}")
        else:
            trays96 = args.plate_tray_number

        if args.standard_replicate_number == None:
            std_reps = 5
            print(f"Using default standard replicate number: {std_reps}")
        else:
            std_reps = args.standard_replicate_number

        if args.trays == None:
            trays = ["R", "G", "B"]
            print(f"Using default available trays: {trays}")
        else:
            trays = args.trays

        if args.technical_replicates_samples == None:
            tech_replicates_samples = 2
            print(f"Using default number of technical replicates for samples: {tech_replicates_samples}")
        else:
            tech_replicates_samples = args.technical_replicates_samples

        main(folder, method, inj_vol, output, trays96, std_reps,trays, tech_replicates_samples)
