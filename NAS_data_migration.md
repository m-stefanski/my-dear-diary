# The Story

I was trying to migrate my data from one WD MyCloud EX 2 Ultra to another. I found that file transfer between both NASes was limited to 25 MB/s. This file is my story of frustration, unanswered questions and a journey through bash + ssh.

## TL;DR

### Results

Starting with 20-25 MB/s using `scp` and `rsync`, finished with 55 MB/s using `rsync` running as daemon on source. See [Solution](#Solution) for details.

### Takeaways
* WD MyCloud EX2 Ultra is severely underpowered if you want to use any form of encrypted transfer, with only one core utilized
* Using `rsync` on both helps to distribute CPU load - so if you are CPU-bound, consider using `rsync://` instead of `rsync+ssh` or `scp`
* To check for network performance, start with `iperf` for throughput, then `ethtool` for hardware layer and then proceed with tuning if necessary
* To check drive performance: `hdparm` and `dd` for read and write speeds, before checking transfer tools
* If you use `dd` to test write speeds, **use reasonable block size**, difference between `1G` and `1M` is huge

## Initial conditions

| Parameter | Source | Target |
|-|-|-|
| Device | WD MyCloud EX2 Ultra | WD MyCloud EX2 Ultra |
| Firmware | 2.31.204 | 2.31.204 |
| Drives | 2 x 3 TB WDC WD30EFRX-68N32N0, FwRev=82.00A82 | 2 x 4 TB WDC WD40EFRX-68N32N0, FwRev=82.00A82 |
| Raid | Raid-1 | Raid-0 |
| Encrypted | No | Yes |
| IP address | 192.168.1.54 | 192.168.1.53 |

Connected using Cat 5E cables via TP-Link TL-SG108 Gigabit switch.

## Testing

First, I enabled ssh access in both NASes via web-ui:

```Settings > Network > SSH```

Default user for WD Mycloud EX2 Ultra is `sshd` so to connect to NAS I used command:

```ssh sshd@192.168.1.53```

To avoid multiple data transfers I logged into target ssh and tried to copy from source using `scp` command:

```
scp -rp sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin /mnt/HD/HD_a2/
```

However, the transfer speed oscillated between 20-25 MB/s. This is way below expected 70 MB/s.

First I checked if network cards indeed connected using 1000 Mbps full-duplex using `ethtool`:

```
# ethtool egiga0
Settings for egiga0:
	(...)
	Speed: 1000Mb/s
	Duplex: Full
	(...)
```

And that the IO and CPU are not saturated (those were already visible with web-ui, but I used `iostat`):

```
# iostat
Linux 3.10.39 (KlinkierChmurka) 	05/05/20 	_armv7l_	(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
          29.23    6.16   28.23    1.36    0.00   35.02
```

```
# iostat -dx /dev/sda 5
Linux 3.10.39 (KlinkierChmurka) 	05/05/20 	_armv7l_	(2 CPU)

Device:         rrqm/s   wrqm/s     r/s     w/s    rkB/s    wkB/s avgrq-sz avgqu-sz   await r_await w_await  svctm  %util
sda               0.55     5.39    4.01   95.83   212.68 10755.40   219.70     0.45    4.53    4.82    4.52   1.19  11.90
```

I then checked if they are properly routing through the switch with `traceroute`:

```
# traceroute 192.168.1.54
traceroute to 192.168.1.54 (192.168.1.54), 30 hops max, 38 byte packets
 1  192.168.1.54 (192.168.1.54)  0.428 ms  0.428 ms  0.391 ms
 ```

Then I enabled jumbo frames in the web-ui and verified they are working using `ping`:

```
# ping -s 8972 192.168.1.54
PING 192.168.1.54 (192.168.1.54): 8972 data bytes
8980 bytes from 192.168.1.54: seq=0 ttl=64 time=0.898 ms
8980 bytes from 192.168.1.54: seq=1 ttl=64 time=2.904 ms
8980 bytes from 192.168.1.54: seq=2 ttl=64 time=0.786 ms
```

To do performance test I stopped the scp pressing `Ctrl-Z` (that would allow me to resume it later using `bg` of `fg`) and ran a network throughput test using `iperf`:

Source: 
```
# iperf -s
------------------------------------------------------------
Server listening on TCP port 5001
TCP window size: 85.3 KByte (default)
------------------------------------------------------------
[  4] local 192.168.1.53 port 5001 connected with 192.168.1.54 port 41261
[ ID] Interval       Transfer     Bandwidth
[  4]  0.0-10.0 sec  1.16 GBytes   991 Mbits/sec
```

Target:
```
# iperf -c 192.168.1.53
------------------------------------------------------------
Client connecting to 192.168.1.53, TCP port 5001
TCP window size: 93.3 KByte (default)
------------------------------------------------------------
[  3] local 192.168.1.54 port 41261 connected with 192.168.1.53 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0-10.0 sec  1.16 GBytes   992 Mbits/sec
```

This would rule out the network bottleneck. I decided to perform test on one large file using both `scp` and `rsync`, which can sometimes outperform `scp`.

```
# cd /mnt/HD/HD_a2/Marcin/
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 37.631790 seconds, 27.2MB/s
```

Starting with `scp`. Speed is consistent with what I obserwe with real data:
```
# scp -rp sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin/1GB_TEST_FILE /mnt/HD/HD_a2/Marcin/1GB_TEST_FILE
sshd@192.168.1.54's password: 
1GB_TEST_FILE                 100% 1024MB  22.2MB/s   00:46 
```

Now `rsync`. Unfortunately, no improvement there:

```
# rsync -a sshd@192.168.1.54:/mnt/HD/HD_a2/Marcin/1GB_TEST_FILE /mnt/HD/HD_a2/Marcin/1GB_TEST_FILE --progress
sshd@192.168.1.54's password: 
receiving incremental file list
1GB_TEST_FILE
  1073741824 100%   21.57MB/s    0:00:47 (xfer#1, to-check=0/1)

sent 30 bytes  received 1073872980 bytes  20851903.11 bytes/sec
total size is 1073741824  speedup is 1.00
```

But wait, didn't the `dd` created the file on source NAS with speed around 27 MB/s? Time to bench the drives.

Source read speed:

```
# hdparm -t /dev/sda

/dev/sda:
Timing buffered disk reads: 538 MB in  3.01 seconds = 178.73 MB/sec
```

Target write speed:

```
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 41.367580 seconds, 24.8MB/s
```

Ok, so it would seem drive writing speed would be at fault. But why? Maybe indexing is at fault. There is a known issue with indexing daemons [1] to break on certain files causing infinite indexing and bringing NAS performance to its knees.

Let's stop them for the time being. 

```
/etc/init.d/wdmcserverd stop
/etc/init.d/wdphotodbmergerd stop
```

To do this permamently, following command were possible in the past:

```
update-rc.d wdphotodbmergerd disable
update-rc.d wdmcserverd disable
```

But with they stopped working in newest firmware revisions.

So there we are. SMB transfers to the drive are faster, 50-70 MB/s, close to advertised. And it would seem that I am not the only one with such problem (SCP slow, SMB fast):

* https://forums.freebsd.org/threads/slow-nfs-smb-afp-but-fast-scp-read-performance.68077/#post-410296

However, the benchmarks around web seem to find scp an rsync much faster than SMB:

* https://squarism.com/2010/02/12/scp-vs-rsync-vs-smb-vs-ftp/

Having depleted my theories I decided to ask WD community:

https://community.wd.com/t/wd-mycloud-ex2-ultra-2x4tb-slow-write-speeds-over-ssh/250988

And since I had too much time on my hands, I decided to redo the disk configuration and start over. This time using RAID-0 with no encryption:

```
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 32.926906 seconds, 31.1MB/s
```

Better, but not great. How about Spanning?

```
# dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 31.453585 seconds, 32.6MB/s
```

Wait, am I doing it right? Let's try again using `sync` and with different block sizes:

1 GB block: 

```
# sync; dd if=/dev/zero of=1GB_TEST_FILE bs=1G count=1; sync
1+0 records in
1+0 records out
1073741824 bytes (1.0GB) copied, 28.212753 seconds, 36.3MB/s
```

1 MB block:

```
# sync; dd if=/dev/zero of=1GB_TEST_FILE bs=1M count=1024; sync
1024+0 records in
1024+0 records out
1073741824 bytes (1.0GB) copied, 5.598899 seconds, 182.9MB/s
```

Bingo. The testing method was wrong. Seems that the drive is perfectly capable of much better write speeds. Back to the transfer method.

Ah, there we have it. It seems that rsync is CPU-bound on this machine, and its speed is butchered by the fact only one CPU core is used. This is the reason why SMB transfer was running circles around it.

https://community.wd.com/t/horrible-rsync-performance-on-wd-cloud-vs-my-book-live/90736/46

Unfortunately there is no way to mount smb or nfs share on MyCloud... 

# Solution

To share the workload between source and target, we will be using rsync protocol  with `rsync` running as a daemon on source.

Some configuration is needed, though:

## On source:

Create file `/etc/rsyncd.conf` and populate it with:

```
pid file = /var/run/rsyncd.pid
lock file = /var/run/rsync.lock
log file = /var/log/rsync.log
port = 12000

[files]
path = /mnt/HD/HD_a2/
comment = RSYNC FILES
read only = true
timeout = 300
gid = root
uid = root
```

Run rsync daemon using command `rsync --daemon`

## On target:

Verify that rsync server is accessible 

```
# rsync --list-only rsync://192.168.1.54
files          	RSYNC FILES
```

Copy test file from desired share (in my case `Marcin`) from one NAS to another:

```
# rsync -a rsync://192.168.1.54:12000/files/Marcin/1GB_TEST_FILE /mnt/HD/HD_a2/Marcin/ --progress
receiving incremental file list
1GB_TEST_FILE
   470220800  44%   56.30MB/s    0:00:10
```

Success! With over double the speed. It is still lower than 90-100 MB/S reported over internet when using SMB, but it should be sufficient for now. 

Copying whole directories is just as easy:

```
rsync -a rsync://192.168.1.54:12000/files/Marcin/ /mnt/HD/HD_a2/Marcin --progress
```

It's been fun. Truly. Time to have a life though.
