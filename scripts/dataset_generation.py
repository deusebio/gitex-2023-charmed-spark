#!/usr/bin/env python

import os
import kaggle
import pandas as pd

kaggle.api.authenticate()

import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--data-folder",
                        help="Local folder where to store the data",
                        default="./data")
    parser.add_argument("--output", "-o",
                        help="Name of the output file (prefix)",
                        default="interpol_case")
    parser.add_argument("--no-cleanup", dest="cleanup",
                        help="Whether temporary files should be left",
                        action="store_false")

    args = parser.parse_args()

    try:
        os.mkdir(args.data_folder)
    except FileExistsError:
        # Directory already exists
        pass


    print("Downloading file from Kaggle...")
    kaggle.api.dataset_download_files('carrie1/ecommerce-data', path=args.data_folder, unzip=True)

    input_file = f"{args.data_folder}/data.csv"
    print(f"Reading file {input_file} ...")
    df = pd.read_csv(
        input_file, on_bad_lines="skip", encoding_errors="ignore"
    )

    print("Processing data ...")
    df["Date"] = pd.to_datetime(df["InvoiceDate"])

    # Patch nations

    df.loc[df[(df["CustomerID"] == 12394.0) & (
                df["Country"] == "Denmark")].index, "Country"] = "Australia"
    df.loc[df[
        (df["CustomerID"] == 12417.0) & (df["Country"] == "Spain")].index, "Country"] = "Australia"

    # Patch Invoice

    to_duplicate = df[df["InvoiceNo"] == "570446"].copy(deep=True)
    to_duplicate.loc[:, "CustomerID"] = 12417.0
    to_duplicate.loc[:, "InvoiceNo"] = "570447"

    to_duplicate_2 = df[df["InvoiceNo"] == "570446"].copy(deep=True)
    to_duplicate_2.loc[:, "CustomerID"] = 12397.0
    to_duplicate_2.loc[:, "InvoiceNo"] = "570445"

    output_file = f"{args.data_folder}/{args.output}.csv.gz"
    print(f"Outputting file {output_file} ...")
    new_dataset = pd.concat(
        [
            df.drop(index=df[df["InvoiceNo"] == "570445"].index),
            to_duplicate, to_duplicate_2
        ]) \
        .sort_values(["Date", "InvoiceNo"]).reset_index(drop=True) \
        .drop(["Date"], axis=1) \
        .to_csv(output_file, index=False, compression="gzip")

    if args.cleanup:
        os.remove(input_file)