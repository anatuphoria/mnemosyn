# Security

## Supported versions

Only the latest release gets fixes. Mnemosyn is in its test phase, so please update before
reporting.

## Reporting a problem

Please do not open a public issue for a security problem. Report it privately through GitHub:
open the [Security tab](https://github.com/anatuphoria/mnemosyn/security/advisories/new) of the
repository and choose "Report a vulnerability". You should get an answer within a week.

## What Mnemosyn does and does not do

1. The app does not connect to the internet. The only links it opens are the ones you choose in
   the Help menu, and they open in your own browser.
2. It keeps your quiz progress, your settings and an error log on your computer, in your user
   folder. Nothing is sent anywhere.
3. Lab experiment files are plain text and are checked when opened. They cannot run code.
4. The downloads are not signed yet. Check a download against `SHA256SUMS.txt` on its release page.
