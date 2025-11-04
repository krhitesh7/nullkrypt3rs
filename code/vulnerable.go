package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// processUserInput processes user input and executes a command
// VULNERABILITY: Command injection - user input is directly used in shell command without sanitization
func processUserInput(filename string) error {
	// Vulnerable: Direct command injection if filename contains shell metacharacters
	cmd := fmt.Sprintf("cat %s", filename)

	// Even more vulnerable: using exec.Command incorrectly
	parts := strings.Fields(cmd)
	if len(parts) < 2 {
		return fmt.Errorf("invalid command")
	}

	// This is vulnerable - filename could contain ; rm -rf / or other malicious commands
	result := exec.Command("sh", "-c", cmd)
	output, err := result.CombinedOutput()
	if err != nil {
		return err
	}

	fmt.Println(string(output))
	return nil
}

// processFileList processes a list of files
// VULNERABILITY: Slice bounds not checked properly
func processFileList(files []string, index int) string {
	// Vulnerable: No bounds checking before accessing slice
	// If index >= len(files), this will panic
	if index < 0 {
		return "Invalid index"
	}
	// Missing check: if index >= len(files)
	return files[index] // Potential panic if index out of bounds
}

// unsafeMemoryAccess demonstrates unsafe memory operations
// VULNERABILITY: Buffer overflow-like vulnerability with slices
func unsafeMemoryAccess(data []byte, size int) {
	buffer := make([]byte, size)
	// Vulnerable: Copying data without checking if it fits in buffer
	// If len(data) > size, this will panic, but worse, if size calculation is wrong,
	// we could overwrite memory
	copy(buffer, data[:size]) // Potential slice bounds issue

	fmt.Printf("Buffer contains: %s\n", string(buffer))
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: ./vulnerable <filename>")
		fmt.Println("Example: ./vulnerable test.txt")
		fmt.Println("VULNERABLE: Try: ./vulnerable 'test.txt; ls -la'")
		os.Exit(1)
	}

	filename := os.Args[1]

	// Demonstrate command injection vulnerability
	fmt.Printf("Processing file: %s\n", filename)
	err := processUserInput(filename)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	// Demonstrate slice bounds vulnerability
	files := []string{"file1.txt", "file2.txt", "file3.txt"}
	// This could cause a panic if index is out of bounds
	result := processFileList(files, 5) // Index 5 doesn't exist!
	fmt.Printf("File at index 5: %s\n", result)
}
