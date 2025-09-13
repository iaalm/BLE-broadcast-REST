use axum::{routing::{get, post}, Json, Router};
use axum::http::StatusCode;
use serde::Deserialize;
use clap::Parser;

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Host address to listen on
    #[arg(short, long, default_value = "0.0.0.0")]
    address: String,

    /// Port to listen on
    #[arg(short, long, default_value_t = 15)]
    port: u16,
}

#[derive(Deserialize)]
struct BroadcastRequest {
    data: String,
    duration: u64,
}

async fn broadcast_handler(Json(payload): Json<BroadcastRequest>) -> StatusCode {
    tokio::spawn(async move {
        let add_adv_cmd = format!("btmgmt add-adv -d {} 1", payload.data);
        let rm_adv_cmd = "btmgmt rm-adv 1".to_string();

        // Execute add-adv command
        let add_adv_output = tokio::process::Command::new("sh")
            .arg("-c")
            .arg(&add_adv_cmd)
            .output()
            .await;

        match add_adv_output {
            Ok(output) => {
                if !output.status.success() {
                    eprintln!("Failed to add advertisement: {}", String::from_utf8_lossy(&output.stderr));
                } else {
                    println!("Successfully added advertisement: {}", String::from_utf8_lossy(&output.stdout));
                }
            }
            Err(e) => {
                eprintln!("Failed to execute add-adv command: {}", e);
            }
        }

        // Wait for specified duration
        tokio::time::sleep(tokio::time::Duration::from_secs(payload.duration)).await;

        // Execute rm-adv command
        let rm_adv_output = tokio::process::Command::new("sh")
            .arg("-c")
            .arg(&rm_adv_cmd)
            .output()
            .await;

        match rm_adv_output {
            Ok(output) => {
                if !output.status.success() {
                    eprintln!("Failed to remove advertisement: {}", String::from_utf8_lossy(&output.stderr));
                } else {
                    println!("Successfully removed advertisement: {}", String::from_utf8_lossy(&output.stdout));
                }
            }
            Err(e) => {
                eprintln!("Failed to execute rm-adv command: {}", e);
            }
        }
    });

    StatusCode::ACCEPTED
}

#[derive(Deserialize)]
struct UdpRequest {
    address: String,
    port: u16,
    data: String,
}

async fn udp_handler(Json(payload): Json<UdpRequest>) -> StatusCode {
    // Create a UDP socket
    let socket = match tokio::net::UdpSocket::bind("0.0.0.0:0").await {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Failed to bind UDP socket: {}", e);
            return StatusCode::INTERNAL_SERVER_ERROR;
        }
    };

    let addr = format!("{}:{}", payload.address, payload.port);
    let data = payload.data.as_bytes();

    match socket.send_to(data, &addr).await {
        Ok(bytes_sent) => {
            println!("Sent {} bytes to {}:{}", bytes_sent, payload.address, payload.port);
            StatusCode::OK
        }
        Err(e) => {
            eprintln!("Failed to send UDP packet to {}:{} : {}", payload.address, payload.port, e);
            StatusCode::INTERNAL_SERVER_ERROR
        }
    }
}

#[tokio::main]
async fn main() {
    let args = Args::parse();

    // build our application with a single route
    let app = Router::new()
        .route("/", get(|| async { "" }))
        .route("/broadcast", post(broadcast_handler))
        .route("/udp", post(udp_handler));
    
    println!("Listening on {}:{}", args.address, args.port);

    // run it with hyper on `localhost:3000`
    let listener = tokio::net::TcpListener::bind(format!("{}:{}", args.address, args.port))
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}
