#!/usr/bin/env python3
import os
import re
import sys

def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Find UserTrackingService writer pattern
    writer_pattern = None
    writer_file = None
    tracking_dir = os.path.join(repo, "UserTrackingService")
    for root, _, files in os.walk(tracking_dir):
        for f in files:
            if f.endswith(".java"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    src = fh.read()
                    # e.g. "ad:cap:" + deviceId + ":" + campaignId
                    # Let's just find anything with "ad:cap:"
                    m = re.search(r'("ad:cap:"\s*\+[^;]+)', src)
                    if m:
                        writer_pattern = re.sub(r'\s+', '', m.group(1))
                        writer_file = path
                        break
        if writer_pattern:
            break

    # 2. Find BiddingEngine reader pattern
    reader_pattern = None
    reader_file = None
    bidding_dir = os.path.join(repo, "BiddingEngine")
    for root, _, files in os.walk(bidding_dir):
        for f in files:
            if f.endswith(".java"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    src = fh.read()
                    m = re.search(r'("ad:cap:"\s*\+[^;)]+)', src)
                    if m:
                        reader_pattern = re.sub(r'\s+', '', m.group(1))
                        reader_file = path
                        break
        if reader_pattern:
            break

    if not writer_pattern:
        print("FAIL: Could not find 'ad:cap:' key construction in UserTrackingService")
        return 1
    if not reader_pattern:
        print("FAIL: Could not find 'ad:cap:' key construction in BiddingEngine")
        return 1

    # Extract variable components
    # We strip out variable names, keeping only the structure, to see if they match exactly.
    # Actually, a better approach is to check if they both concatenate the exact same sequence of types,
    # or just let the script report if they aren't identical (since they might use different local variable names)
    
    def normalize(pat):
        # normalize common naming differences
        pat = pat.replace('event.getDeviceId()', 'deviceId')
        pat = pat.replace('request.getDeviceId()', 'deviceId')
        pat = pat.replace('event.getCampaignId()', 'campaignId')
        pat = pat.replace('request.getCampaignId()', 'campaignId')
        return pat

    if normalize(writer_pattern) != normalize(reader_pattern):
        print(f"FAIL: Redis key pattern mismatch!\n  Writer ({os.path.basename(writer_file)}): {writer_pattern}\n  Reader ({os.path.basename(reader_file)}): {reader_pattern}")
        return 1

    print("PASS: Redis key patterns match between UserTrackingService and BiddingEngine")
    return 0

if __name__ == "__main__":
    sys.exit(main())
