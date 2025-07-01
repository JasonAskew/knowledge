#!/usr/bin/env python3
"""
Test script to demonstrate enhanced validation reporting
"""

import subprocess
import sys
import os

def test_validation_reporting():
    """Test that validation reports are always generated"""
    
    print("="*60)
    print("Testing Enhanced Validation Reporting")
    print("="*60)
    
    # Test 1: Run with validation-only mode
    print("\nTest 1: Running validation-only mode...")
    result = subprocess.run([
        sys.executable, "enhanced_test_runner.py",
        "--validation-only"
    ], capture_output=True, text=True)
    
    print("Output:", result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    
    # Test 2: Run full test with deprecated --no-validation flag
    print("\nTest 2: Running full test with --no-validation (should show warning)...")
    result = subprocess.run([
        sys.executable, "enhanced_test_runner.py",
        "--no-validation",
        "--search-type", "vector"
    ], capture_output=True, text=True)
    
    # Check for deprecation warning
    if "WARNING: --no-validation flag is DEPRECATED" in result.stdout:
        print("✅ Deprecation warning shown correctly")
    else:
        print("❌ Deprecation warning not found")
    
    # Test 3: Normal run (validation should be mandatory)
    print("\nTest 3: Normal test run (validation should be mandatory)...")
    result = subprocess.run([
        sys.executable, "enhanced_test_runner.py",
        "--search-type", "vector"
    ], capture_output=True, text=True)
    
    # Check for validation report generation
    if "VALIDATION REPORT GENERATION COMPLETE" in result.stdout:
        print("✅ Validation report generated")
    else:
        print("❌ Validation report not generated")
    
    # Check for report paths in output
    if "validation_report_" in result.stdout:
        print("✅ Validation report path shown")
    else:
        print("❌ Validation report path not shown")
    
    print("\n" + "="*60)
    print("Testing complete. Check ../data/test_results/ for generated reports.")
    print("="*60)

if __name__ == "__main__":
    # Change to the script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_validation_reporting()