# Test video

Place a PLAX echocardiography cine here with the exact filename:

`plax.avi`

The application reads its native FPS, reopens the AVI at EOF, and uses the most
recent five seconds of acquired frames for each analysis. A short AVI that loops
several times can test playback and integration, but is not a medically valid
continuous five-second cardiac cine. Patient-identifying data should not be used
in this prototype.
