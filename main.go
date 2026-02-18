package main

import (
	"fmt"
	"log"
	"net"
	"os"
)

func main() {
	// Check if port argument is provided
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <port>\n", os.Args[0])
		os.Exit(1)
	}

	port := os.Args[1]
	address := fmt.Sprintf(":%s", port)

	// Start listening on the specified port
	listener, err := net.Listen("tcp", address)
	if err != nil {
		log.Fatalf("Failed to listen on %s: %v", address, err)
	}
	defer listener.Close()

	log.Printf("Listening on port %s", port)

	// Accept connections and close them immediately
	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Printf("Failed to accept connection: %v", err)
			continue
		}

		// Close the connection immediately
		conn.Close()
	}
}
