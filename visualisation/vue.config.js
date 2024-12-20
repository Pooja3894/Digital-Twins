// Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau
// LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.


// Webpack configuration file for bundling code
const CopyWebpackPlugin = require('copy-webpack-plugin');
const NodePolyfillPlugin = require('node-polyfill-webpack-plugin')
const path = require('path');

const cesiumSource = 'node_modules/cesium/Source';

/**
 * @type {import('@vue/cli-service').ProjectOptions}
 */
module.exports = {
  configureWebpack: {
    plugins: [
      new NodePolyfillPlugin(),
      new CopyWebpackPlugin({
        patterns: [
          {from: path.join(cesiumSource, '../Build/Cesium/Workers'), to: 'Workers'},
          {from: path.join(cesiumSource, 'Assets'), to: 'Assets'},
          {from: path.join(cesiumSource, 'Widgets'), to: 'Widgets'}
        ]
      })
    ]
  },
  chainWebpack(config) {
   // Add rule so that the LICENSE text can be read into a WebPage
   config.module
      .rule('raw')
      .test(/LICENSE$/)
      .use('raw-loader')
      .loader('raw-loader')
      .end()
  }
}
