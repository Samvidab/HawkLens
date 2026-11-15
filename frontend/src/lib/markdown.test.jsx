// @vitest-environment jsdom
import React from 'react'
import {it,expect} from 'vitest'
import {render,screen} from '@testing-library/react'
import {Markdown} from './markdown'
it('renders recorded memo headings and adjacent appendix tables without flattening the table into prose',()=>{
 render(<Markdown text={'# Saved memo\n\n## Upgrades\n| Building | Cost |\n|---|---|\n| Recorded fixture | $120 |'} />)
 expect(screen.getByRole('heading',{name:'Saved memo'})).toBeTruthy()
 expect(screen.getByRole('heading',{name:'Upgrades'})).toBeTruthy()
 expect(screen.getByRole('table')).toBeTruthy()
 expect(screen.getByRole('cell',{name:'$120'})).toBeTruthy()
})
