/* Local Natural Earth basemap. Data: https://www.naturalearthdata.com/
 * Separate script assets work from file:// without fetch/CORS or API keys.
 */
window.MRMSNaturalEarth = {
  createLayer(L) {
    const data = window.MRMSNaturalEarthData;
    const NaturalEarthLayer = L.Layer.extend({
      onAdd(map) {
        this.map = map;
        const pane = map.getPane('naturalEarth') || map.createPane('naturalEarth');
        pane.style.zIndex = 210; // Below radar overlays (400) and location markers.
        pane.style.pointerEvents = 'none';
        map.getContainer().classList.add('natural-earth-map');
        this.geography = L.layerGroup([
          L.geoJSON(data.countries, {pane: 'naturalEarth', interactive: false,
            style: {color: '#596475', weight: 1, opacity: 0.8,
              fillColor: '#19232e', fillOpacity: 1}}),
          L.geoJSON(data.states, {pane: 'naturalEarth', interactive: false,
            style: {color: '#596475', weight: 0.7, opacity: 0.6, fill: false}}),
        ]).addTo(map);
        this.labels = L.layerGroup().addTo(map);
        this.redrawLabels = () => this.updateLabels();
        map.on('moveend', this.redrawLabels);
        this.updateLabels();
      },
      updateLabels() {
        this.labels.clearLayers();
        const map = this.map, zoom = map.getZoom(), bounds = map.getBounds();
        const occupied = [];
        // Largest cities first; omit overlapping labels at the current zoom.
        for (const [name, lon, lat, minZoom] of data.places) {
          if (minZoom > zoom || !bounds.contains([lat, lon])) continue;
          const p = map.latLngToContainerPoint([lat, lon]);
          const width = name.length * 6 + 12;
          const box = [p.x, p.y - 8, p.x + width, p.y + 8];
          if (occupied.some(b => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
          occupied.push(box);
          const label = document.createElement('span');
          label.textContent = '\u00b7 ' + name;
          L.marker([lat, lon], {pane: 'naturalEarth', interactive: false, keyboard: false,
            icon: L.divIcon({className: 'natural-earth-label', html: label,
              iconSize: [width, 16], iconAnchor: [0, 8]})}).addTo(this.labels);
        }
      },
      onRemove(map) {
        map.off('moveend', this.redrawLabels);
        map.removeLayer(this.geography);
        map.removeLayer(this.labels);
        map.getContainer().classList.remove('natural-earth-map');
        this.map = null;
      },
    });
    return new NaturalEarthLayer();
  },
};
