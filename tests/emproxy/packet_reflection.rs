//! Runs against unmodified upstream EMProxy with a real encrypted UDP exchange.
//! It does not execute Stash or inject packets into an iOS kernel.
use base64::{engine::general_purpose::STANDARD, Engine};
use boringtun::{noise::{Tunn, TunnResult}, x25519::{PublicKey, StaticSecret}};
use std::{net::{Ipv4Addr, SocketAddrV4, UdpSocket}, time::{Duration, Instant}};

fn key(s: &str) -> [u8; 32] { STANDARD.decode(s.trim()).unwrap().try_into().unwrap() }
fn checksum(data: &[u8]) -> u16 {
    let mut sum: u32 = data.chunks(2).map(|b| u16::from_be_bytes([b[0], *b.get(1).unwrap_or(&0)]) as u32).sum();
    while sum > 0xffff { sum = (sum & 0xffff) + (sum >> 16); }
    !(sum as u16)
}
fn syn() -> Vec<u8> {
    let mut p = vec![0u8; 40];
    p[0] = 0x45; p[2..4].copy_from_slice(&40u16.to_be_bytes()); p[8] = 64; p[9] = 6;
    p[12..16].copy_from_slice(&[10,7,0,10]); p[16..20].copy_from_slice(&[10,7,0,1]);
    p[20..22].copy_from_slice(&40000u16.to_be_bytes()); p[22..24].copy_from_slice(&62078u16.to_be_bytes());
    p[27] = 1; p[32] = 0x50; p[33] = 0x02; p[34..36].copy_from_slice(&65535u16.to_be_bytes());
    let mut pseudo = p[12..20].to_vec(); pseudo.extend_from_slice(&[0,6,0,20]); pseudo.extend_from_slice(&p[20..]);
    p[36..38].copy_from_slice(&checksum(&pseudo).to_be_bytes());
    let c = checksum(&p[..20]); p[10..12].copy_from_slice(&c.to_be_bytes()); p
}
#[test]
fn encrypted_syn_is_reflected_not_terminated_as_tcp() {
    let reservation = UdpSocket::bind("127.0.0.1:0").unwrap();
    let port = reservation.local_addr().unwrap().port(); drop(reservation);
    let mut handle = em_proxy::start_loopback(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port)).unwrap();
    let socket = UdpSocket::bind("127.0.0.1:0").unwrap();
    socket.connect((Ipv4Addr::LOCALHOST, port)).unwrap();
    socket.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
    let secret = StaticSecret::from(key(include_str!("../keys/client_privatekey")));
    let public = PublicKey::from(key(include_str!("../keys/server_publickey_client")));
    let mut client = Tunn::new(secret, public, None, None, 1, None);
    let packet = syn(); let mut out = [0u8; 4096]; let mut incoming = [0u8; 4096];
    if let TunnResult::WriteToNetwork(b) = client.encapsulate(&packet, &mut out) {
        socket.send(b).unwrap();
    } else { panic!("client failed to initiate WireGuard"); }
    let deadline = Instant::now() + Duration::from_secs(10);
    let reflected = 'receive: loop {
        assert!(Instant::now() < deadline, "no reflected packet");
        let n = socket.recv(&mut incoming).expect("EMProxy handshake/reflection timed out");
        let mut input = &incoming[..n];
        loop {
            match client.decapsulate(None, input, &mut out) {
                TunnResult::WriteToNetwork(b) => { socket.send(b).unwrap(); }
                TunnResult::WriteToTunnelV4(b, _) => break 'receive b.to_vec(),
                TunnResult::Done => break,
                TunnResult::Err(e) => panic!("WireGuard error: {e:?}"),
                _ => panic!("unexpected IPv6"),
            }
            input = &[];
        }
    };
    handle.sender.send(()).unwrap(); handle.join_handle.take().unwrap().join().unwrap();
    let mut expected = packet.clone();
    expected[12..16].copy_from_slice(&packet[16..20]);
    expected[16..20].copy_from_slice(&packet[12..16]);
    assert_eq!(reflected, expected, "upstream should only swap IPv4 endpoints");
    assert_eq!(reflected[33], 0x02, "reflection is SYN, not a SYN-ACK");
    assert_eq!(&reflected[20..24], &packet[20..24], "ports are not swapped");
    println!("Real WG handshake passed; EMProxy returned reflected SYN to 10.7.0.10:62078. No iOS service or Stash was exercised.");
}
